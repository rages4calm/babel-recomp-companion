"""Private packet-based native scenery/fog/radar preview, without game/UI wiring.

Camera-mask mode is a visibility diagnostic, NOT line-of-sight or permanently
earned exploration. Collision-zero mode shows only currently unobstructed
collision cells, NOT a complete walkability/optical-opacity classification.
Saved state is diagnostic only. Its layout identity conservatively binds actual
map-cell and metatile-definition bytes, dimensions, packing and authored crop.
"""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,shutil,struct,subprocess,zlib

ROOT=Path(__file__).resolve().parents[1]
U8=C.c_uint8;U16=C.c_uint16;U32=C.c_uint32;SZ=C.c_size_t;P8=C.POINTER(U8)
class Identity(C.Structure):
    _fields_=[('content',U8*32),('layout',U8*32),('floor',U32)]
class Discovery(C.Structure):
    _fields_=[('identity',Identity),('width',U16),('height',U16),('bits',U8*8192)]
class Color(C.Structure):
    _fields_=[(x,U8)for x in ('r','g','b','a')]
class Transform(C.Structure):
    _fields_=[('x',C.c_int32),('y',C.c_int32),('origin_den',U16),('scale_num',U16),('scale_den',U16)]
class Marker(C.Structure):
    _fields_=[('x',C.c_int16),('y',C.c_int16),('radius',U8),('color',Color)]
class Source(C.Structure):
    _fields_=[('discovery',C.POINTER(Discovery)),('rgba',P8),('rgba_bytes',SZ),('rgba_stride',SZ),('cell',U8),('walkable',P8),('walk_bytes',SZ),('walk_stride',SZ),('markers',C.POINTER(Marker)),('marker_count',SZ),('player_present',C.c_bool),('player_x',C.c_int16),('player_y',C.c_int16)]
class Settings(C.Structure):
    _fields_=[('mode',C.c_int),('transform',Transform),('fog',Color),('floor',Color),('wall',Color),('player',Color),('radius',U8)]
class Scenery(C.Structure):
    _fields_=[('ram',P8),('ram_bytes',SZ),('vram',C.POINTER(U16)),('cgram',C.POINTER(U16)),('vram_words',SZ),('cgram_words',SZ)]+[(x,C.c_uint)for x in ('width','height','map','definitions','characters')]

WRAPPER=r'''
#include <stddef.h>
#include <string.h>
#include "iog_map_discovery.h"
#include "iog_map_view.h"
#include "iog_map_scenery.h"
#include "snes/ppu.h"
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
EXPORT size_t preview_size(unsigned n){
 const size_t sizes[]={sizeof(IogMapDiscoveryIdentity),sizeof(IogMapDiscovery),sizeof(IogMapViewColor),sizeof(IogMapViewTransform),sizeof(IogMapViewMarker),sizeof(IogMapViewSource),sizeof(IogMapViewSettings),sizeof(IogMapScenerySource)};
 return n<sizeof(sizes)/sizeof(sizes[0])?sizes[n]:0;
}
EXPORT unsigned preview_characters(const uint8_t*regs,unsigned physical){Ppu p;memset(&p,0,sizeof(p));memcpy(&p,regs,PPU_SAVESTATE_REGS_SIZE);return PPU_bgTileAdr(&p,physical);}
EXPORT bool preview_init(IogMapDiscovery*m,unsigned w,unsigned h,const IogMapDiscoveryIdentity*i){return IogMapDiscoveryInit(m,w,h,i);}
EXPORT bool preview_reveal(IogMapDiscovery*m,int x,int y,unsigned r,const uint8_t*v,size_t b,size_t s,size_t*n){return IogMapDiscoveryReveal(m,x,y,r,v,b,s,n);}
EXPORT size_t preview_size_encoded(const IogMapDiscovery*m){return IogMapDiscoveryEncodedSize(m);}
EXPORT bool preview_save(const IogMapDiscovery*m,uint8_t*d,size_t b,size_t*n){return IogMapDiscoverySerialize(m,d,b,n);}
EXPORT bool preview_scenery(const IogMapScenerySource*s,unsigned x,unsigned y,unsigned w,unsigned h,unsigned step,uint32_t*d,size_t b,size_t stride){return IogMapSceneryRender(s,x,y,w,h,step,d,b,stride);}
EXPORT bool preview_view(uint8_t*d,size_t b,size_t stride,unsigned w,unsigned h,const IogMapViewSource*s,const IogMapViewSettings*v){return IogMapViewRender(d,b,stride,w,h,s,v);}
'''

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def u16(data,at):return struct.unpack_from('<H',data,at)[0]
def layout_identity(ram,scene,crop):
    width,height=u16(ram,0x692),u16(ram,0x696)
    assert width>0 and height>0 and not(width&255 or height&255)
    map_address,definitions=u16(ram,0x69e),u16(ram,0x6ae)
    map_bytes=(width//256)*(height//256)*256
    assert map_bytes==u16(ram,0x69a)and map_address+map_bytes<=len(ram)
    assert definitions+256*8<=len(ram)
    description={'scene':scene,'crop':list(crop),'map_dimensions':[width,height],
        'cell_world_pixels':16,'packing':'256px pages of row-major16x16 metatiles',
        'map_address':map_address,'map_bytes':map_bytes,'definitions_address':definitions,
        'definitions_bytes':256*8,
        'map_sha256':hashlib.sha256(ram[map_address:map_address+map_bytes]).hexdigest(),
        'definitions_sha256':hashlib.sha256(ram[definitions:definitions+256*8]).hexdigest()}
    encoded=json.dumps(description,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(encoded).digest(),description
def png(path,w,h,rgba):
    def chunk(tag,b):return struct.pack('>I',len(b))+tag+b+struct.pack('>I',zlib.crc32(tag+b))
    scan=b''.join(b'\0'+rgba[y*w*4:(y+1)*w*4]for y in range(h))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
def ppm(path,w,h,rgba):
    rgb=bytearray(w*h*3)
    for i in range(3):rgb[i::3]=rgba[i::4]
    path.write_bytes(f'P6\n{w} {h}\n255\n'.encode()+rgb)
def buffer(data):return (U8*len(data)).from_buffer_copy(data)
def bind(dll,name,result,args):
    f=getattr(dll,name);f.restype=result;f.argtypes=args;return f

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--compiler',default='cc');p.add_argument('--step',type=int,choices=(1,2),default=2)
    p.add_argument('--crop',help='Authored pixel rectangle x,y,width,height; default uses captured camera bounds')
    visibility=p.add_mutually_exclusive_group(required=True);visibility.add_argument('--explored-mask',type=Path);visibility.add_argument('--camera-mask',action='store_true')
    radar=p.add_mutually_exclusive_group(required=True);radar.add_argument('--walkable-mask',type=Path);radar.add_argument('--radar-collision-zero',action='store_true')
    p.add_argument('--markers',type=Path,help='Explicit local-cell marker JSON; undiscovered markers remain hidden')
    a=p.parse_args();compiler=shutil.which(a.compiler)
    if not compiler:p.error('compiler executable not found')
    a.compiler=str(Path(compiler).resolve());out=a.out.resolve();private=(ROOT/'.local').resolve()
    if not out.is_relative_to(private):p.error('outputs must stay private under ignored .local/')
    out.mkdir(parents=True,exist_ok=False)
    prefix=a.packet.resolve();meta_file=Path(str(prefix)+'.source.json');active_file=Path(str(prefix)+'.active.wram.bin');epoch_file=Path(str(prefix)+'.epochs.bin')
    if not all(x.is_relative_to(private)for x in (prefix,meta_file,active_file,epoch_file)):p.error('packet inputs must remain under ignored .local/')
    meta=json.loads(meta_file.read_text());assert meta['schema']=='iog-world-source-v1'and meta['ready']and meta['complete']and meta['epoch_bytes']==131584
    assert isinstance(meta['epochs'],int)and 1<=meta['epochs']<=16 and len(meta['lines'])==225
    assert active_file.stat().st_size==131072 and epoch_file.stat().st_size==meta['epochs']*131584
    active=active_file.read_bytes();epochs=epoch_file.read_bytes();assert len(active)==131072 and len(epochs)==meta['epochs']*131584
    line=meta['lines'][1];epoch_index=line['epoch'];assert 0<=epoch_index<meta['epochs'];epoch=epochs[epoch_index*131584:(epoch_index+1)*131584]
    ram=epoch[66048:];vram=epoch[:65536];cgram=epoch[65536:66048];regs=bytes.fromhex(line['regs']);assert len(regs)==64 and regs[4]&7==1
    width,height=u16(ram,0x692),u16(ram,0x696);assert 0<width<=4096 and 0<height<=4096 and not(width&255 or height&255)
    assert u16(active,0x644)==meta['scene']==u16(ram,0x644)
    assert all(u16(active,at)==u16(ram,at)for at in (0x692,0x696,0x69e,0x6ae))
    if a.crop:crop=tuple(map(int,a.crop.split(',')))
    else:
        left,top,right,bottom=(u16(ram,n)for n in (0x6d6,0x6d8,0x6da,0x6de));crop=(left,top,right-left,bottom-top)
    assert len(crop)==4;cx,cy,cw,ch=crop
    assert cx>=0 and cy>=0 and cw>0 and ch>0 and cx+cw<=width and cy+ch<=height and not any(n&15 for n in crop)
    gw,gh=cw//16,ch//16;assert 0<gw<=256 and 0<gh<=256
    inputs={str(x):sha(x)for x in (meta_file,active_file,epoch_file)}
    if a.explored_mask:
        assert a.explored_mask.stat().st_size==gw*gh
        visible=a.explored_mask.read_bytes();inputs[str(a.explored_mask.resolve())]=sha(a.explored_mask)
        visibility_label='explicit supplied exploration mask; provenance belongs to caller'
    else:
        camx,camy=u16(active,0x68a),u16(active,0x68e)
        visible=bytes(int(cx+x*16>=camx and cy+y*16>=camy and cx+(x+1)*16<=camx+256 and cy+(y+1)*16<=camy+224)for y in range(gh)for x in range(gw))
        visibility_label='camera-rectangle diagnostic only; no LOS/optical-visibility or permanently earned exploration claim'
    (out/'explored-mask.bin').write_bytes(visible)
    if a.walkable_mask:
        assert a.walkable_mask.stat().st_size==gw*gh
        walk=a.walkable_mask.read_bytes();inputs[str(a.walkable_mask.resolve())]=sha(a.walkable_mask)
        radar_label='explicit caller-supplied binary walkability mask'
    else:
        # Stock live collision grid, one page-packed byte per16x16 cell.
        # Nonzero classes include slopes, ledges and occupied cells: they
        # are not all walls and this is deliberately a coarse diagnostic.
        assert active[0x80:0x83]==b'\x00\xc0\x7f'
        page_width=active[0x693];grid_size=u16(active,0x69a);assert grid_size==(width//256)*(height//256)*256 and grid_size<=0x4000
        values=[]
        for y in range(gh):
            for x in range(gw):
                tx,ty=cx//16+x,cy//16+y;index=(((ty>>4)*page_width+(tx>>4))<<8)|((ty&15)<<4)|(tx&15)
                assert index<grid_size and index<0x4000
                values.append(int(active[0x1c000+index]==0))
        walk=bytes(values);radar_label='live collision-byte-zero diagnostic; nonzero special/partial/occupied cells shown together, not full walkability or LOS'
    (out/'radar-mask.bin').write_bytes(walk)
    sources=[ROOT/'src'/name for name in ('iog_map_scenery.c','iog_map_scenery.h','iog_map_discovery.c','iog_map_discovery.h','iog_map_view.c','iog_map_view.h')]
    sources.extend(ROOT/'snesrecomp/runner/src/snes'/name for name in ('ppu.h','ppu_register_fields.inc'))
    source_hashes={str(x.relative_to(ROOT)):sha(x)for x in sources+[Path(__file__)]}
    wrapper=out/'preview.c';wrapper.write_text(WRAPPER);library=out/'preview.dll';cmd=[a.compiler,'-shared','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),'-I'+str(ROOT/'snesrecomp/runner/src'),str(wrapper),*[str(x)for x in sources if x.suffix=='.c'],'-o',str(library)]
    built=subprocess.run(cmd,capture_output=True,text=True,timeout=120);(out/'build.log').write_text(built.stdout+built.stderr);built.check_returncode();dll=C.CDLL(str(library))
    native_size=bind(dll,'preview_size',SZ,[C.c_uint]);assert all(native_size(i)==C.sizeof(t)for i,t in enumerate((Identity,Discovery,Color,Transform,Marker,Source,Settings,Scenery)))
    init=bind(dll,'preview_init',C.c_bool,[C.POINTER(Discovery),C.c_uint,C.c_uint,C.POINTER(Identity)])
    reveal=bind(dll,'preview_reveal',C.c_bool,[C.POINTER(Discovery),C.c_int,C.c_int,C.c_uint,P8,SZ,SZ,C.POINTER(SZ)])
    decode=bind(dll,'preview_scenery',C.c_bool,[C.POINTER(Scenery)]+[C.c_uint]*5+[C.POINTER(U32),SZ,SZ])
    draw=bind(dll,'preview_view',C.c_bool,[P8,SZ,SZ,C.c_uint,C.c_uint,C.POINTER(Source),C.POINTER(Settings)])
    identity=Identity();identity.content[:]=bytes.fromhex((ROOT/'rom_identity.txt').read_text().split('expected_sha256',1)[1].split('=',1)[1].split()[0])
    layout_digest,layout_description=layout_identity(ram,meta['scene'],crop)
    identity.layout[:]=layout_digest;identity.floor=cy//16
    discovery=Discovery();assert init(C.byref(discovery),gw,gh,C.byref(identity));visible_buffer=buffer(visible);changed=SZ();assert reveal(C.byref(discovery),gw//2,gh//2,512,visible_buffer,len(visible),gw,C.byref(changed))
    raw=buffer(ram);vr=(U16*32768).from_buffer_copy(vram);cg=(U16*256).from_buffer_copy(cgram);registers=buffer(regs)
    character_base=bind(dll,'preview_characters',C.c_uint,[P8,C.c_uint])(registers,(ram[0x6ee]>>7)&1)
    scenery=Scenery(raw,len(ram),vr,cg,32768,256,width,height,u16(ram,0x69e),u16(ram,0x6ae),character_base)
    aw,ah=cw//a.step,ch//a.step;native_atlas=(U32*(aw*ah))();assert decode(C.byref(scenery),cx,cy,cw,ch,a.step,native_atlas,C.sizeof(native_atlas),aw*4)
    bgrx=bytes(native_atlas);rgba=bytearray(bgrx);rgba[0::4]=bgrx[2::4];rgba[2::4]=bgrx[0::4];rgba=bytes(rgba)
    png(out/'scenery-atlas-private.png',aw,ah,rgba)
    atlas=buffer(rgba);collision=buffer(walk);source=Source();source.discovery=C.pointer(discovery);source.rgba=atlas;source.rgba_bytes=len(rgba);source.rgba_stride=aw*4;source.cell=16//a.step;source.walkable=collision;source.walk_bytes=len(walk);source.walk_stride=gw
    marker_storage=None
    if a.markers:
        records=json.loads(a.markers.read_text());assert isinstance(records,list)and len(records)<=256;marker_storage=(Marker*len(records))()
        for i,m in enumerate(records):
            values=[m['x'],m['y'],m.get('radius',2)];color=m.get('rgba',[255,190,70,255])
            assert all(type(x)is int for x in values+color)and -32768<=values[0]<=32767 and -32768<=values[1]<=32767 and 0<=values[2]<=8 and len(color)==4 and all(0<=x<=255 for x in color)
            marker_storage[i]=Marker(*values,Color(*color))
        source.markers=marker_storage;source.marker_count=len(records);inputs[str(a.markers.resolve())]=sha(a.markers)
    source.player_present=True;source.player_x=u16(active,0x9a2)//16-cx//16;source.player_y=u16(active,0x9a4)//16-cy//16
    scale=min(16//a.step,2048//max(gw,gh));ow,oh=gw*scale,gh*scale;assert 0<ow<=2048 and 0<oh<=2048
    settings=Settings();settings.transform=Transform(0,0,1,scale,1);settings.fog=Color(12,15,23,255);settings.floor=Color(75,110,125,255);settings.wall=Color(115,127,142,255);settings.player=Color(255,220,60,255);settings.radius=2
    images={}
    for mode,name in ((0,'scenery-explored'),(1,'radar-explored')):
        settings.mode=mode;dst=(U8*(ow*oh*4))();assert draw(dst,len(dst),ow*4,ow,oh,C.byref(source),C.byref(settings));pixels=bytes(dst);png(out/(name+'.png'),ow,oh,pixels);ppm(out/(name+'.ppm'),ow,oh,pixels);images[name]={'width':ow,'height':oh,'png_sha256':sha(out/(name+'.png'))}
    size=bind(dll,'preview_size_encoded',SZ,[C.POINTER(Discovery)])(C.byref(discovery));state=(U8*size)();written=SZ();assert bind(dll,'preview_save',C.c_bool,[C.POINTER(Discovery),P8,SZ,C.POINTER(SZ)])(C.byref(discovery),state,size,C.byref(written));assert written.value==size;(out/'exploration-diagnostic.iogmap').write_bytes(bytes(state))
    assert source_hashes=={str(x.relative_to(ROOT)):sha(x)for x in sources+[Path(__file__)]},'sources changed during native preview'
    compiler_version=subprocess.run([a.compiler,'--version'],capture_output=True,text=True,check=True,timeout=20).stdout
    result={'passed':True,'scene':meta['scene'],'frame':meta['frame'],'crop':crop,'camera':[u16(active,0x68a),u16(active,0x68e)],'primary_layer_only':True,'grid':[gw,gh],'revealed_cells':changed.value,'visibility':visibility_label,'radar':radar_label,'player_cell':[source.player_x,source.player_y],'atlas_step':a.step,'hud_and_entities_in_atlas':False,'images':images,'inputs':inputs,'sources':source_hashes,'native_build_command':cmd,'native_library_sha256':sha(library),'wrapper_sha256':sha(wrapper),'compiler_sha256':sha(a.compiler),'compiler_version':compiler_version,'content_identity_source':'Original-USA project profile; packet provenance is not cryptographically authenticated by this preview','scope':'Packet-based native decoder/discovery/compositor integration only. No live game/UI integration, automatic LOS, earned gameplay exploration or full rendered-scene equivalence.'}
    result.update(diagnostic_state_only=True,layout_sha256=layout_digest.hex(),layout_identity_inputs=layout_description)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ('passed','scene','frame','crop','grid','revealed_cells','visibility','radar','images')},indent=2))
if __name__=='__main__':main()
