#include "iog_map_view.h"
#include <string.h>

static bool Overlap(const void*a,size_t an,const void*b,size_t bn)
{
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return an&&bn&&(x<=y?y-x<an:x-y<bn);
}
static bool Fits(size_t bytes,size_t stride,size_t row,unsigned height,size_t *needed)
{
    if(!height||stride<row||(height>1&&stride>(SIZE_MAX-row)/(height-1)))return false;
    *needed=(size_t)(height-1)*stride+row;
    return bytes>=*needed;
}
static int64_t Floor(int64_t n,int64_t d){return n>=0?n/d:-((-n+d-1)/d);}
static int64_t Coordinate(const IogMapViewTransform*t,int pixel,bool vertical)
{
    int32_t origin=vertical?t->origin_y_numerator:t->origin_x_numerator;
    return (int64_t)2*origin*t->scale_numerator+
        (int64_t)(2*pixel+1)*t->scale_denominator*t->origin_denominator;
}
static int Cell(const IogMapViewTransform*t,int pixel,bool vertical)
{
    return (int)Floor(Coordinate(t,pixel,vertical),
        (int64_t)2*t->origin_denominator*t->scale_numerator);
}
static int Center(const IogMapViewTransform*t,int cell,bool vertical)
{
    int32_t origin=vertical?t->origin_y_numerator:t->origin_x_numerator;
    int64_t n=((int64_t)(2*cell+1)*t->origin_denominator-2*(int64_t)origin)*t->scale_numerator;
    return (int)Floor(n,(int64_t)2*t->origin_denominator*t->scale_denominator);
}
static void Pixel(uint8_t*p,IogMapViewColor c){p[0]=c.r;p[1]=c.g;p[2]=c.b;p[3]=255;}
static void Blend(uint8_t*p,const uint8_t*c)
{
    for(unsigned i=0;i<3;i++)p[i]=(uint8_t)(((unsigned)c[i]*c[3]+(unsigned)p[i]*(255-c[3])+127)/255);
    p[3]=255;
}
static void Marker(uint8_t*dst,size_t stride,unsigned w,unsigned h,
    const IogMapViewSource*s,const IogMapViewTransform*t,int cx,int cy,
    unsigned radius,IogMapViewColor color,bool player)
{
    if(cx<0||cy<0||cx>=s->discovery->width||cy>=s->discovery->height)return;
    if(!player&&!IogMapDiscoveryIsRevealed(s->discovery,cx,cy))return;
    int x0=Center(t,cx,false),y0=Center(t,cy,true);
    for(int y=y0-(int)radius;y<=y0+(int)radius;y++)
        for(int x=x0-(int)radius;x<=x0+(int)radius;x++){
            int dx=x-x0,dy=y-y0;
            if(x<0||y<0||(unsigned)x>=w||(unsigned)y>=h||
               (unsigned)(dx*dx+dy*dy)>radius*radius)continue;
            if(!player&&!IogMapDiscoveryIsRevealed(s->discovery,Cell(t,x,false),Cell(t,y,true)))continue;
            uint8_t rgba[4]={color.r,color.g,color.b,color.a};Blend(dst+(size_t)y*stride+(unsigned)x*4,rgba);
        }
}
bool IogMapViewRender(uint8_t*dst,size_t bytes,size_t stride,unsigned w,unsigned h,
    const IogMapViewSource*s,const IogMapViewSettings*v)
{
    size_t target,atlas=0,walkable=0;
    if(!dst||!s||!v||!s->discovery||!w||!h||w>2048||h>2048||
       !IogMapDiscoveryEncodedSize(s->discovery)||!Fits(bytes,stride,(size_t)w*4,h,&target))return false;
    const IogMapViewTransform*t=&v->transform;
    if(!t->origin_denominator||t->origin_denominator>256||!t->scale_numerator||
       t->scale_numerator>1024||!t->scale_denominator||t->scale_denominator>256||
       t->origin_x_numerator < -(int32_t)256*t->origin_denominator||
       t->origin_x_numerator > (int32_t)256*t->origin_denominator||
       t->origin_y_numerator < -(int32_t)256*t->origin_denominator||
       t->origin_y_numerator > (int32_t)256*t->origin_denominator||
       v->player_radius_pixels>8||s->marker_count>256||(!s->markers&&s->marker_count))return false;
    for(size_t i=0;i<s->marker_count;i++)if(s->markers[i].radius_pixels>8)return false;
    unsigned mw=s->discovery->width,mh=s->discovery->height,cell=s->scenery_cell_pixels;
    if(v->mode==kIogMapViewScenery){
        if(!s->scenery_rgba||!cell||cell>16||
           !Fits(s->scenery_bytes,s->scenery_stride,(size_t)mw*cell*4,mh*cell,&atlas))return false;
    }else if(v->mode==kIogMapViewRadar){
        if(!s->walkable||!Fits(s->walkable_bytes,s->walkable_stride,mw,mh,&walkable))return false;
    }else return false;
    if(Overlap(dst,target,s,sizeof(*s))||Overlap(dst,target,v,sizeof(*v))||
       Overlap(dst,target,s->discovery,sizeof(*s->discovery))||
       Overlap(dst,target,s->scenery_rgba,atlas)||Overlap(dst,target,s->walkable,walkable)||
       Overlap(dst,target,s->markers,s->marker_count*sizeof(*s->markers)))return false;
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
        uint8_t*p=dst+(size_t)y*stride+x*4;Pixel(p,v->fog);
        int gx=Cell(t,(int)x,false),gy=Cell(t,(int)y,true);
        if(!IogMapDiscoveryIsRevealed(s->discovery,gx,gy))continue;
        if(v->mode==kIogMapViewRadar){Pixel(p,s->walkable[(size_t)gy*s->walkable_stride+(unsigned)gx]?v->floor:v->wall);}
        else{
            int64_t denominator=(int64_t)2*t->origin_denominator*t->scale_numerator;
            size_t sx=(size_t)Floor(Coordinate(t,(int)x,false)*cell,denominator);
            size_t sy=(size_t)Floor(Coordinate(t,(int)y,true)*cell,denominator);
            Blend(p,s->scenery_rgba+sy*s->scenery_stride+sx*4);
        }
    }
    for(size_t i=0;i<s->marker_count;i++){
        const IogMapViewMarker*m=&s->markers[i];
        Marker(dst,stride,w,h,s,t,m->cell_x,m->cell_y,m->radius_pixels,m->color,false);
    }
    if(s->player_present)Marker(dst,stride,w,h,s,t,s->player_x,s->player_y,
        v->player_radius_pixels,v->player,true);
    return true;
}
