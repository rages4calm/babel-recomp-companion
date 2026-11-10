#include "iog_world_view.h"
#include <string.h>

static int32_t Origin(int32_t camera,uint32_t map,unsigned view,unsigned native)
{
    if(map<view) return -(int32_t)((view-map)/2);
    int32_t origin=camera-(int32_t)((view-native)/2);
    if(origin<0) origin=0;
    if(origin>(int32_t)(map-view)) origin=(int32_t)(map-view);
    return origin;
}

bool IogWorldViewCompute(int32_t camera_x,int32_t camera_y,
    uint32_t map_width,uint32_t map_height,uint16_t width,uint16_t height,
    IogWorldView *out)
{
    if(!out) return false;
    memset(out,0,sizeof(*out));
    if(width<256 || width>2048 || height<224 || height>512 ||
       map_width<256 || map_height<224 || map_width>65535 || map_height>65535 ||
       camera_x<0 || camera_y<0 || (uint32_t)camera_x>map_width-256 ||
       (uint32_t)camera_y>map_height-224) return false;
    out->width=width;out->height=height;
    out->world_x=Origin(camera_x,map_width,width,256);
    out->world_y=Origin(camera_y,map_height,height,224);
    out->native_x=(uint16_t)(camera_x-out->world_x);
    out->native_y=(uint16_t)(camera_y-out->world_y);
    if(out->world_x<0) out->padding_left=(uint16_t)-out->world_x;
    if(out->world_y<0) out->padding_top=(uint16_t)-out->world_y;
    if(out->world_x+width>(int32_t)map_width)
        out->padding_right=(uint16_t)(out->world_x+width-map_width);
    if(out->world_y+height>(int32_t)map_height)
        out->padding_bottom=(uint16_t)(out->world_y+height-map_height);
    return true;
}
