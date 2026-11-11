"""Free-first image batches. No paid fallback; no cross-provider scene mixing.

Only image generation is changed. Narration, renderer and publication remain
owned by the existing application. All errors exclude URLs, bodies and keys.
"""
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse, quote
import uuid

import requests
from PIL import Image, ImageOps, ImageStat

CONFIG = Path(__file__).with_name('minomasal_images.json')
OVH_CATALOG = 'https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/stable-diffusion-xl/'
OVH_URL = 'https://stable-diffusion-xl.endpoints.kepler.ai.cloud.ovh.net/api/text2image'
CF_MODEL = '@cf/black-forest-labs/flux-1-schnell'
CF_DEFAULT_STEPS = 4  # Minimum prompt-only request uses the documented model default.
MAX_BYTES = 20 * 1024 * 1024
STYLE = ("Colorful children's animated storybook illustration, emerald green, sky blue and warm coral palette; "
         "same character design, clothing, fur and body proportions in every scene; no extra main characters; "
         "full-bleed environment, no text, no border. Compose for a vertical 9:16 crop: "
         "keep all characters and important action inside the central 50 percent width.")


class ImageFailure(RuntimeError):
    pass


class ProviderFailure(ImageFailure):
    def __init__(self, provider, reason, status=None, api_errors=None):
        self.provider, self.reason, self.status = provider, reason, status
        self.api_errors = api_errors or []
        detail = 'bakiye/kredi yetersiz; tekrar denenmedi' if status == 402 else reason
        super().__init__(f'{provider}: ' + (f'HTTP {status}: ' if status else '') + detail)


def load_config():
    try:
        config=json.loads(CONFIG.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        raise ImageFailure('Görsel yapılandırması okunamadı.') from None
    allowed={'schema_version','order','output_size','min_source_side','cloudflare_steps',
             'pollinations_enabled','pollinations_max_pollen_per_request','approved_for_automation'}
    if not isinstance(config,dict) or set(config)-allowed:
        raise ImageFailure('Görsel yapılandırmasında bilinmeyen alan var.')
    override=os.environ.get('MINOMASAL_IMAGE_PROVIDERS')
    if override is not None:
        config['order']=[v.strip() for v in override.split(',') if v.strip()]
    order=config.get('order')
    if (config.get('schema_version') != 1 or not isinstance(order,list) or not order
            or len(set(order)) != len(order) or any(p not in PROVIDERS for p in order)):
        raise ImageFailure('Geçersiz görsel sağlayıcı yapılandırması.')
    approved=config.get('approved_for_automation')
    if not isinstance(approved,list) or any(p not in PROVIDERS for p in approved):
        raise ImageFailure('Otomasyon kalite onay listesi geçersiz.')
    if config.get('output_size') != [1080,1920] or config.get('min_source_side') != 512:
        raise ImageFailure('Görsel boyutu güvenlik ayarları geçersiz.')
    if type(config.get('cloudflare_steps')) is not int or not 1<=config['cloudflare_steps']<=8:
        raise ImageFailure('Cloudflare adım sayısı geçersiz.')
    return config


def ensure_production_config(local=''):
    if local:
        return
    config=load_config()
    if not any(name in config['approved_for_automation'] for name in config['order']):
        raise ImageFailure('automation_quality_not_approved; üretim başlamadan durduruldu.')


def identity():
    """Cache identity intentionally contains no API keys or hashes of keys."""
    config=load_config()
    return {'engine':2,'config':config,'style':STYLE,'cloudflare_framing':'contain',
            'comfy_checkpoint':os.environ.get('COMFYUI_CHECKPOINT',''),
            'cloudflare_free_confirmed':os.environ.get('MINOMASAL_CLOUDFLARE_FREE_PLAN_CONFIRMED')=='true'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def cloudflare_error_details(response):
    """Export only numeric API codes and locally defined messages, never raw text.

    Even an upstream message echoing a token fragment, header, URL, account or
    prompt cannot enter logs. Unknown messages stay redacted; field mentions
    are selected from a fixed schema vocabulary.
    """
    known={10000:'Authentication error',5007:'No such model or task',
           5004:'Invalid input data type',3003:'Request is missing headers or body',
           5018:'Account is not allowed to access this model',5016:'Model agreement required',
           3023:'Service unavailable for account',3041:'Account is not allowed to access this model',
           5035:'Model requires a Workers Paid plan',3036:'Daily free allocation exhausted',
           3040:'Capacity temporarily exceeded'}
    try:
        if len(response.content)>MAX_BYTES:return []
        body=response.json()
        if not isinstance(body,dict) or not isinstance(body.get('errors'),list):return []
        result=[]
        for error in body['errors'][:4]:
            if not isinstance(error,dict):continue
            code=error.get('code')
            if type(code) is not int or not 0<=code<=1_000_000:continue
            message=error.get('message')
            mentions=[field for field in ('prompt','steps','seed','width','height')
                      if isinstance(message,str) and re.search(r'\b'+field+r'\b',message,re.I)]
            result.append({'code':code,'message':known.get(code,'Unrecognized API error; raw message withheld'),
                           'message_is_canonical':True,'schema_fields_mentioned':mentions})
        return result
    except (ValueError,TypeError):
        return []


def http(provider, method, url, *, before=None, attempts=3, **kwargs):
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("Invalid bounded retry count")
    for attempt in range(attempts):
        if before: before()
        try:
            # Redirects may forward credentials or reach unapproved services.
            response=requests.request(method,url,timeout=180,allow_redirects=False,**kwargs)
        except requests.RequestException:
            raise ProviderFailure(provider,'connection_failed') from None
        status=response.status_code
        if status==200:
            if len(response.content)>MAX_BYTES:
                raise ProviderFailure(provider,'response_too_large')
            return response
        if status in (429,500,502,503,504) and attempt<attempts-1:
            time.sleep(3 * 2**attempt)
            continue
        # 402/403 disable this candidate for the remainder of this entire batch.
        details=cloudflare_error_details(response) if provider=='cloudflare' else []
        raise ProviderFailure(provider,'request_failed',status,api_errors=details)
    raise ProviderFailure(provider,'retry_limit')


def json_response(response, provider):
    try:
        value=response.json()
        if not isinstance(value,dict): raise ValueError()
        return value
    except (ValueError,TypeError):
        raise ProviderFailure(provider,'invalid_json') from None


def decode64(value, provider):
    try:
        if not isinstance(value,str): raise ValueError()
        return base64.b64decode(value,validate=True)
    except (ValueError,TypeError):
        raise ProviderFailure(provider,'invalid_image_encoding') from None


def contain_box(size):
    """Content rectangle on 1080x1920 canvas, preserving all source pixels."""
    if (len(size)!=2 or any(type(side) is not int or side<=0 for side in size)):
        raise ImageFailure('Geçersiz kaynak ölçüsü.')
    scale=min(1080/size[0],1920/size[1])
    width=max(1,min(1080,round(size[0]*scale)))
    height=max(1,min(1920,round(size[1]*scale)))
    return [(1080-width)//2,(1920-height)//2,width,height]


def normalize(data, path, *, framing='crop'):
    """Structural quality checks, not a claim of semantic character validation."""
    if framing not in ('crop','contain'):raise ImageFailure('Bilinmeyen kadraj yöntemi.')
    if not data or len(data)>MAX_BYTES: raise ImageFailure('Görsel boş veya çok büyük.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if min(image.size)<512 or image.width*image.height>16_000_000:
                raise ImageFailure('Görsel boyutu geçersiz.')
            image.verify()
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image=ImageOps.exif_transpose(source).convert('RGB')
            if max(ImageStat.Stat(image.resize((64,64))).stddev)<1:
                raise ImageFailure('Boş/tek renk görsel; yayın engellendi.')
            size=list(image.size)
            if framing=='contain':
                left,top,width,height=contain_box(size)
                # Solid matte avoids generating duplicate blurred characters
                # in a background layer. Nothing from the source is cropped.
                vertical=Image.new('RGB',(1080,1920),(24,45,38))
                vertical.paste(image.resize((width,height),Image.Resampling.LANCZOS),(left,top))
            else:
                vertical=ImageOps.fit(image,(1080,1920),method=Image.Resampling.LANCZOS)
            tmp=path.with_suffix('.tmp.jpg');vertical.save(tmp,quality=95);tmp.replace(path)
        validate_file(path)
        return size
    except (OSError,ValueError,Image.DecompressionBombError):
        raise ImageFailure('Görsel bütünlüğü doğrulanamadı.') from None


def validate_file(path):
    try:
        with Image.open(path) as image:
            if image.size!=(1080,1920): raise ImageFailure('Dikey görsel boyutu geçersiz.')
            image.verify()
    except (OSError,ValueError):
        raise ImageFailure('Eksik veya bozuk görsel.') from None


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','head'): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','head'): self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


@dataclass
class Provider:
    config: dict
    key: str = field(default='',repr=False)
    model: str = ''
    seed: int = 1234
    name = 'base'
    supports_seed = False
    def preflight(self):
        raise NotImplementedError
    def generate(self,prompt,index):
        raise NotImplementedError


class OVHcloud(Provider):
    name='ovhcloud'
    def preflight(self):
        self.model='stable-diffusion-xl-base-v10'
        # Zero billing exposure: this adapter deliberately never sends an OVH key.
        # Model-specific public catalogue must still say Free on this run.
        response=http(self.name,'GET',OVH_CATALOG)
        parser=VisibleText();parser.feed(response.text)
        text=' '.join(' '.join(parser.parts).split())
        sections=[text[m.start():m.start()+2500] for m in re.finditer(re.escape(self.model),text)]
        if not any(re.search(r'\bPricing\s+Free\b',section) for section in sections):
            raise ProviderFailure(self.name,'current_free_price_unverified')
        self.last_request=None
    def throttle(self):
        now=time.monotonic()
        if self.last_request is not None:
            time.sleep(max(0,31-(now-self.last_request)))
        self.last_request=time.monotonic()
    def generate(self,prompt,index):
        return http(self.name,'POST',OVH_URL,before=self.throttle,
                    headers={'Accept':'application/octet-stream'},
                    json={'prompt':prompt,'negative_prompt':'text, watermark, border, extra limbs, duplicate main character'}).content


def verify_cloudflare_free_plan(data):
    subscriptions=data.get('result')
    info=data.get('result_info')
    if data.get('success') is not True or not isinstance(subscriptions,list):
        raise ProviderFailure('cloudflare','complete_free_plan_proof_required')
    # The documented single-page endpoint lists all subscriptions. result_info
    # is optional. When supplied, its count must still prove a complete list.
    if info is not None:
        if not isinstance(info,dict):
            raise ProviderFailure('cloudflare','complete_free_plan_proof_required')
        # All metadata properties are optional in the single-page API schema.
        # An empty metadata object is equivalent to omitted metadata, not a
        # partial page. Supplied counts/pages must nevertheless be consistent.
        for field in ('total_count','count'):
            if field in info and (type(info[field]) is not int or info[field]!=len(subscriptions)):
                raise ProviderFailure('cloudflare','complete_free_plan_proof_required')
        if 'page' in info and (type(info['page']) is not int or info['page']!=1):
            raise ProviderFailure('cloudflare','complete_free_plan_proof_required')
    for subscription in subscriptions:
        if not isinstance(subscription,dict): raise ProviderFailure('cloudflare','unbilled_account_required')
        plan=subscription.get('rate_plan',{})
        if (not isinstance(plan,dict) or plan.get('id')!='free' or plan.get('public_name')!='Workers Free'
                or plan.get('scope')!='account' or type(subscription.get('price')) not in (int,float)
                or subscription['price']!=0 or plan.get('externally_managed') is not False
                or plan.get('is_contract') is not False or subscription.get('state')!='Provisioned'):
            raise ProviderFailure('cloudflare','paid_or_unknown_subscription_blocked')
    return 'unbilled_account' if not subscriptions else 'workers_free'


class Cloudflare(Provider):
    name='cloudflare'
    supports_seed=False  # Minimum REST schema: prompt only; no seed claim.
    def preflight(self):
        self.model=CF_MODEL
        self.account=os.environ.get('CLOUDFLARE_ACCOUNT_ID','')
        self.token=os.environ.get('CLOUDFLARE_API_TOKEN','')
        if not re.fullmatch(r'[a-fA-F0-9]{32}',self.account) or not self.token:
            raise ProviderFailure(self.name,'credentials_missing')
        usage_token=os.environ.get('CLOUDFLARE_USAGE_TOKEN','').strip()
        if not usage_token:
            raise ProviderFailure(self.name,'usage_token_missing')
        if usage_token==self.token:
            raise ProviderFailure(self.name,'usage_token_must_be_distinct')
        # The inference token is never sent to billing/analytics endpoints.
        data=json_response(http(self.name,'GET',f'https://api.cloudflare.com/client/v4/accounts/{self.account}/subscriptions',
                                headers={'Authorization':'Bearer '+usage_token}),self.name)
        verify_cloudflare_free_plan(data)
        from minomasal_cloudflare_usage import query_quota
        self.quota=query_quota(self.account,usage_token)
        reserve=max(1000,self.config.get('scene_count',10)*3*2*(19.2+9.6*CF_DEFAULT_STEPS))
        if self.quota['remaining_neurons_reported']<reserve:
            raise ProviderFailure(self.name,'insufficient_verified_free_quota')

    def generate(self,prompt,index):
        if not isinstance(prompt,str) or not 1<=len(prompt)<=2048:
            raise ProviderFailure(self.name,'prompt_outside_documented_schema')
        response=http(self.name,'POST',f'https://api.cloudflare.com/client/v4/accounts/{self.account}/ai/run/{self.model}',
                      headers={'Authorization':'Bearer '+self.token},
                      json={'prompt':prompt},
                      attempts=self.config.get('http_attempts',3))
        data=json_response(response,self.name)
        if data.get('success') is not True: raise ProviderFailure(self.name,'model_failed')
        result=data.get('result')
        if not isinstance(result,dict): raise ProviderFailure(self.name,'invalid_image_response')
        return decode64(result.get('image'),self.name)


class ComfyUI(Provider):
    name='comfyui'
    supports_seed=True
    def preflight(self):
        self.url=os.environ.get('COMFYUI_URL','http://127.0.0.1:8188').rstrip('/')
        parsed=urlparse(self.url)
        # Local, self-hosted only. No hosted credit service, API/partner nodes.
        if (parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1')
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ProviderFailure(self.name,'local_server_required')
        self.model=os.environ.get('COMFYUI_CHECKPOINT','')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\.safetensors',self.model):
            raise ProviderFailure(self.name,'local_checkpoint_required')
        http(self.name,'GET',self.url+'/system_stats')
    def workflow(self,prompt):
        # Core nodes only. The checkpoint/LoRA licence remains the operator's responsibility.
        return {
            '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':self.model}},
            '2':{'class_type':'CLIPTextEncode','inputs':{'text':prompt,'clip':['1',1]}},
            '3':{'class_type':'CLIPTextEncode','inputs':{'text':'text, watermark, extra limbs','clip':['1',1]}},
            '4':{'class_type':'EmptyLatentImage','inputs':{'width':768,'height':1344,'batch_size':1}},
            '5':{'class_type':'KSampler','inputs':{'model':['1',0],'positive':['2',0],'negative':['3',0],
                'latent_image':['4',0],'seed':self.seed,'steps':20,'cfg':7,'sampler_name':'euler','scheduler':'normal','denoise':1}},
            '6':{'class_type':'VAEDecode','inputs':{'samples':['5',0],'vae':['1',2]}},
            '7':{'class_type':'SaveImage','inputs':{'images':['6',0],'filename_prefix':'MinoMasal'}},
        }
    def generate(self,prompt,index):
        # A submission is not retried after 5xx: it may already be queued.
        # http's bounded retry is safe for read-only polling, not queue writes.
        try:
            response=requests.request('POST',self.url+'/prompt',json={'prompt':self.workflow(prompt)},timeout=30,allow_redirects=False)
        except requests.RequestException:
            raise ProviderFailure(self.name,'submission_ambiguous') from None
        if response.status_code!=200: raise ProviderFailure(self.name,'submission_failed',response.status_code)
        data=json_response(response,self.name);pid=data.get('prompt_id')
        if not isinstance(pid,str) or not re.fullmatch(r'[A-Za-z0-9-]+',pid):
            raise ProviderFailure(self.name,'invalid_prompt_id')
        for _ in range(60):
            history=json_response(http(self.name,'GET',self.url+'/history/'+pid),self.name).get(pid)
            if history:
                status=history.get('status',{})
                if status.get('status_str')=='error': raise ProviderFailure(self.name,'workflow_failed')
                images=history.get('outputs',{}).get('7',{}).get('images',[])
                if status.get('completed') is True and len(images)==1:
                    item=images[0]
                    if item.get('type')!='output': raise ProviderFailure(self.name,'unexpected_output')
                    return http(self.name,'GET',self.url+'/view',params={k:item[k] for k in ('filename','subfolder','type')}).content
            time.sleep(5)
        raise ProviderFailure(self.name,'workflow_timeout')


class Pollinations(Provider):
    name='pollinations'
    supports_seed=True
    def preflight(self):
        # No inference request without provable FREE source AND a hard per-key cap.
        # Existing account total alone may contain purchased credits: insufficient proof.
        if self.config.get('pollinations_enabled') is not True or not self.key:
            raise ProviderFailure(self.name,'disabled_free_budget_unverified')
        if not re.fullmatch(r'[A-Za-z0-9/_.-]+',self.model):
            raise ProviderFailure(self.name,'single_explicit_model_required')
        cap=self.config.get('pollinations_max_pollen_per_request')
        if type(cap) not in (int,float) or not math.isfinite(cap) or cap<=0:
            raise ProviderFailure(self.name,'bounded_cost_configuration_required')
        headers={'Authorization':'Bearer '+self.key}
        key=json_response(http(self.name,'GET','https://gen.pollinations.ai/account/key',headers=headers),self.name)
        balance=json_response(http(self.name,'GET','https://gen.pollinations.ai/account/balance',headers=headers),self.name)
        account=balance.get('accountBalance')
        if not isinstance(account,dict):
            raise ProviderFailure(self.name,'free_only_capped_budget_unverified')
        # Fail closed if API schema/scope does not prove no purchased balance and
        # a finite, exhausted-at-zero key budget covering the maximum retries.
        required=cap * self.config['scene_count'] * 3
        budget=key.get('pollenBudget')
        available=balance.get('balance')
        tier=account.get('tier')
        if (key.get('valid') is not True or type(account.get('paid')) not in (int,float) or account.get('paid')!=0
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in (budget,available,tier))
                or not required<=budget<=tier or available<required):
            raise ProviderFailure(self.name,'free_only_capped_budget_unverified')
    def generate(self,prompt,index):
        return http(self.name,'GET','https://gen.pollinations.ai/image/'+quote(prompt,safe=''),
                    headers={'Authorization':'Bearer '+self.key},
                    params={'model':self.model,'width':1080,'height':1920,'seed':self.seed,
                            'nologo':'true'}).content


PROVIDERS={'ovhcloud':OVHcloud,'cloudflare':Cloudflare,'comfyui':ComfyUI,'pollinations':Pollinations}


def make_images(story,folder,key,model,local='',seed=1234):
    from minomasal import validate
    validate(story)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    config=load_config();config['scene_count']=len(story['scenes'])
    characters=story['characters'] if isinstance(story['characters'],str) else json.dumps(story['characters'],ensure_ascii=False,sort_keys=True)
    bible={'characters':characters,'style':STYLE,'seed':seed}
    visual_profile=story.get('visual_profile')
    planned_prompts=None
    if visual_profile is not None:
        from minomasal_visual_profile import build_prompt, profile_digest, review_contract
        try:
            planned_prompts=[build_prompt(visual_profile,{'action':scene['visual'],
                'inventory':scene.get('visual_inventory')}) for scene in story['scenes']]
            bible.update(visual_profile=visual_profile,profile_sha256=profile_digest(visual_profile),
                         quality_review=review_contract())
        except ValueError:
            raise ImageFailure('Görsel profili veya açık sahne envanteri geçersiz.') from None
    request={'story':story,'bible':bible,'pipeline':identity(),'pollinations_model':model}
    if local:
        supplied=sorted(p for p in Path(local).glob('*') if p.suffix.lower() in ('.png','.jpg','.jpeg','.webp'))
        if len(supplied)!=len(story['scenes']): raise ImageFailure('Yerel görsel/sahne sayısı eşleşmiyor.')
        request['local_hashes']=[sha(p) for p in supplied]
    signature=hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    manifest=folder/'images.json'
    if manifest.exists():
        try:
            saved=json.loads(manifest.read_text(encoding='utf-8'))
            if saved.get('signature')==signature and len(saved['images'])==len(story['scenes']):
                paths=[]
                for i,item in enumerate(saved['images'],1):
                    path=folder/f'{i:02}.jpg'
                    if item['sha256']!=sha(path): raise ImageFailure('Önbellek görseli değişmiş.')
                    validate_file(path);paths.append(path)
                return paths
        except (ValueError,KeyError,OSError,TypeError,AttributeError):
            raise ImageFailure('Görsel önbelleği bozuk; yayın engellendi.') from None
    errors=[]
    candidates=['local'] if local else config['order']
    for name in candidates:
        attempt=folder/'attempts'/f'{name}-{uuid.uuid4().hex[:12]}'
        provider=None
        try:
            if name!='local':
                if name not in config['approved_for_automation']:
                    raise ProviderFailure(name,'automation_quality_not_approved')
                provider=PROVIDERS[name](config,key,model,seed);provider.preflight()
            attempt.mkdir(parents=True)
            write_json(attempt/'character_bible.json',bible)
            images=[]
            for i,scene in enumerate(story['scenes'],1):
                prompt=planned_prompts[i-1] if planned_prompts else f'CHARACTER BIBLE (unchanged): {characters}. SCENE: {scene["visual"]}. {STYLE}'
                if provider:
                    data=provider.generate(prompt,i)
                else:
                    data=supplied[i-1].read_bytes()
                raw=attempt/f'{i:02}.source';raw.write_bytes(data)
                path=attempt/f'{i:02}.jpg'
                source_size=normalize(data,path,framing='contain' if name=='cloudflare' else 'crop')
                images.append({'path':path,'source_size':source_size})
            # Never expose a half batch to render. Prior provider attempts are retained.
            result=[];records=[]
            for i,item in enumerate(images,1):
                path=folder/f'{i:02}.jpg';tmp=path.with_suffix('.tmp.jpg')
                tmp.write_bytes(item['path'].read_bytes());tmp.replace(path)
                result.append(path);records.append({'sha256':sha(path),'source_size':item['source_size']})
            write_json(manifest,{'schema_version':1,'signature':signature,'provider':name,
                'model':provider.model if provider else 'local','character_bible':bible,
                'generation_seed':seed if provider and provider.supports_seed else None,
                'framing':'contain' if name=='cloudflare' else 'crop',
                'attempt':str(attempt.relative_to(folder)),'images':records,
                'created_at_utc':datetime.now(timezone.utc).isoformat()})
            print(f'Görsel paketi hazır: {name}, {len(result)} sahne; sağlayıcı karışımı yok.')
            return result
        except ProviderFailure as exc:
            errors.append(str(exc))
        except ImageFailure:
            errors.append(f'{name}: image_quality_failed')
    raise ImageFailure('Görsel üretimi durduruldu; ücretli geçiş yok. ' + '; '.join(errors))
