/* SPDX-License-Identifier: MIT */
#include "companion_achievement_presentation.h"
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
enum { ROWS=5, TOAST_MS=5500, REPEAT_DELAY=350, REPEAT_RATE=90 };
static const uint32_t BG=0xff101a28u, FG=0xffe2ecf1u, DIM=0xff91a3b6u,
    ACCENT=0xff65ddc3u, GOLD=0xffffcf77u, SELECTED=0xff203548u, LINE=0xff314357u;

bool ca_ui_init(ca_ui *ui,const ca_definition *definitions,const ca_ui_metadata *metadata,size_t count) {
    if(!ui||count>CA_MAX_ACHIEVEMENTS||(!definitions&&count))return false;
    for(size_t i=0;i<count;i++)if(!definitions[i].id||!definitions[i].title||
        !definitions[i].description||!definitions[i].target)return false;
    memset(ui,0,sizeof *ui);ui->definitions=definitions;ui->metadata=metadata;ui->count=count;return true;
}
bool ca_ui_snapshot(ca_ui *ui,const ca_state *states,size_t count) {
    if(!ui||count!=ui->count||(!states&&count))return false;
    for(size_t i=0;i<count;i++)if(states[i].progress>ui->definitions[i].target||
        ((states[i].progress==ui->definitions[i].target)!=(states[i].unlocked_at!=0)))return false;
    if(count)memcpy(ui->states,states,count*sizeof *states);return true;
}
bool ca_ui_notice(ca_ui *ui,size_t index) {
    if(!ui||index>=ui->count||!ui->states[index].unlocked_at)return false;
    uint64_t bit=UINT64_C(1)<<index;
    if(ui->announced&bit)return true;
    if(ui->queued==CA_MAX_ACHIEVEMENTS)return false;
    ui->queue[ui->queued++]=index;ui->announced|=bit;return true;
}
void ca_ui_open(ca_ui *ui,uint32_t held) {
    if(!ui)return;ui->open=true;ui->selected=0;ui->previous_input=held;ui->repeat_armed=false;
}
void ca_ui_close(ca_ui *ui) {if(ui){ui->open=false;ui->repeat_armed=false;}}
void ca_ui_command_apply(ca_ui *ui,ca_ui_command command) {
    if(!ui||!ui->open)return;
    if(command==CA_UI_DISMISS){ca_ui_close(ui);return;}
    if(!ui->count){ui->selected=0;return;}
    size_t last=ui->count-1;
    if(ui->selected>last)ui->selected=last;
    switch(command){
    case CA_UI_FIRST:ui->selected=0;break;
    case CA_UI_LAST:ui->selected=last;break;
    case CA_UI_PREVIOUS_ROW:ui->selected=ui->selected?ui->selected-1:last;break;
    case CA_UI_NEXT_ROW:ui->selected=(ui->selected+1)%ui->count;break;
    case CA_UI_PREVIOUS_PAGE:case CA_UI_NEXT_PAGE:{
        size_t pages=(ui->count+ROWS-1)/ROWS,page=ui->selected/ROWS,offset=ui->selected%ROWS;
        page=command==CA_UI_PREVIOUS_PAGE?(page?page-1:pages-1):(page+1)%pages;
        ui->selected=page*ROWS+offset;if(ui->selected>last)ui->selected=last;break;
    }
    default:break;
    }
}
bool ca_ui_tick(ca_ui *ui,uint32_t buttons,uint32_t now,bool blocked) {
    if(!ui)return false;
    bool pause=blocked||ui->open, started=false;
    if(ui->toast_active){
        if(pause&&!ui->paused)ui->pause_started=now;
        else if(!pause&&ui->paused)ui->toast_started+=now-ui->pause_started;
        /* Tick on every host frame, including hidden frames; intervals <2^31ms. */
        if(!pause&&(uint32_t)(now-ui->toast_started)>=TOAST_MS)ui->toast_active=false;
    }
    ui->paused=pause;
    if(!ui->toast_active&&!pause&&ui->queued){
        ui->toast_index=ui->queue[0];
        memmove(ui->queue,ui->queue+1,--ui->queued*sizeof ui->queue[0]);
        ui->toast_started=now;ui->toast_active=true;started=true;
    }
    if(ui->open){
        uint32_t edge=buttons&~ui->previous_input,nav=buttons&(CA_UI_UP|CA_UI_DOWN|CA_UI_LEFT|CA_UI_RIGHT);
        if(edge&CA_UI_CLOSE)ca_ui_close(ui);
        else{
            if(edge&nav){ui->repeat_at=now+REPEAT_DELAY;ui->repeat_armed=true;}
            else if(nav&&ui->repeat_armed&&(int32_t)(now-ui->repeat_at)>=0){edge|=nav;ui->repeat_at=now+REPEAT_RATE;}
            if(!nav)ui->repeat_armed=false;
            if(edge&CA_UI_UP)ca_ui_command_apply(ui,CA_UI_PREVIOUS_ROW);
            else if(edge&CA_UI_DOWN)ca_ui_command_apply(ui,CA_UI_NEXT_ROW);
            if(edge&CA_UI_LEFT)ca_ui_command_apply(ui,CA_UI_PREVIOUS_PAGE);
            else if(edge&CA_UI_RIGHT)ca_ui_command_apply(ui,CA_UI_NEXT_PAGE);
        }
    }
    ui->previous_input=buttons;return started;
}
static void rect(const ca_ui_draw *d,int x,int y,int w,int h,uint32_t c){d->rectangle(d->context,x,y,w,h,c);}
static void text(const ca_ui_draw *d,int x,int y,int w,int h,const char *s,uint32_t c){d->text(d->context,x,y,w,h,s?s:"",c);}
static const char *title(const ca_ui *ui,size_t i) {
    const ca_ui_metadata *m=ui->metadata?ui->metadata+i:NULL;
    return m&&m->secret&&!ui->states[i].unlocked_at?(m->locked_title?m->locked_title:"Hidden achievement"):ui->definitions[i].title;
}
static const char *description(const ca_ui *ui,size_t i) {
    const ca_ui_metadata *m=ui->metadata?ui->metadata+i:NULL;
    return m&&m->secret&&!ui->states[i].unlocked_at?(m->locked_description?m->locked_description:"Keep exploring to discover this achievement."):ui->definitions[i].description;
}
bool ca_ui_draw_browser(const ca_ui *ui,const ca_ui_draw *d,const char *heading,const char *status) {
    if(!ui||!ui->open||!d||!d->rectangle||!d->text)return false;
    char label[96];size_t earned=0;for(size_t i=0;i<ui->count;i++)earned+=ui->states[i].unlocked_at!=0;
    rect(d,0,0,640,360,BG);rect(d,0,0,640,4,ACCENT);
    text(d,28,20,584,24,heading?heading:"ACHIEVEMENTS",ACCENT);
    snprintf(label,sizeof label,"%zu OF %zu EARNED",earned,ui->count);text(d,28,48,584,20,label,FG);
    size_t first=ui->selected/ROWS*ROWS;
    for(size_t i=first;i<ui->count&&i<first+ROWS;i++){
        int y=80+(int)(i-first)*38;bool unlocked=ui->states[i].unlocked_at!=0;
        if(i==ui->selected)rect(d,16,y-4,608,35,SELECTED);
        rect(d,30,y+4,10,10,unlocked?GOLD:DIM);
        text(d,56,y,544,16,title(ui,i),unlocked?GOLD:FG);
        if(unlocked)snprintf(label,sizeof label,"EARNED");
        else if(ui->definitions[i].target>1)snprintf(label,sizeof label,"%u / %u",ui->states[i].progress,ui->definitions[i].target);
        else snprintf(label,sizeof label,"LOCKED");
        text(d,56,y+16,260,14,label,DIM);
        if(!unlocked&&ui->definitions[i].target>1){
            rect(d,336,y+21,248,4,LINE);
            int progress=(int)((uint64_t)248*ui->states[i].progress/ui->definitions[i].target);
            if(progress)rect(d,336,y+21,progress,4,ACCENT);
        }
    }
    if(!ui->count)text(d,28,100,584,28,"Achievements are not available in this session.",DIM);
    snprintf(label,sizeof label,"PAGE %zu / %zu",ui->count?ui->selected/ROWS+1:0,(ui->count+ROWS-1)/ROWS);
    text(d,28,272,584,16,label,ACCENT);
    if(ui->count)text(d,28,293,584,30,description(ui,ui->selected),DIM);
    text(d,28,325,584,14,status?status:"Local progress",DIM);
    text(d,28,344,584,14,"UP/DOWN: SELECT   LEFT/RIGHT: PAGE   BACK: CLOSE",FG);return true;
}
bool ca_ui_draw_toast(const ca_ui *ui,const ca_ui_draw *d) {
    if(!ui||!ui->toast_active||ui->paused||ui->open||!d||!d->rectangle||!d->text)return false;
    rect(d,0,0,144,32,GOLD);rect(d,1,1,142,30,BG);
    text(d,6,3,132,9,"ACHIEVEMENT UNLOCKED",ACCENT);
    text(d,6,14,132,16,ui->definitions[ui->toast_index].title,FG);return true;
}
bool ca_ui_toast_origin(int x,int y,int w,int h,int scale,int *out_x,int *out_y) {
    if(!out_x||!out_y||scale<1||scale>INT_MAX/(CA_TOAST_WIDTH+8)||
       w<(CA_TOAST_WIDTH+8)*scale||h<(CA_TOAST_HEIGHT+8)*scale)return false;
    int64_t ox=(int64_t)x+w-(CA_TOAST_WIDTH+4)*scale,oy=(int64_t)y+4*scale;
    if(ox<INT_MIN||ox>INT_MAX||oy<INT_MIN||oy>INT_MAX)return false;
    *out_x=(int)ox;*out_y=(int)oy;return true;
}
bool ca_chime_generate(int16_t *samples,size_t capacity) {
    if(!samples||capacity<CA_CHIME_FRAMES)return false;
    const double notes[]={523.2511306,659.2551138,783.9908720};
    for(unsigned i=0;i<CA_CHIME_FRAMES;i++){
        double value=0;
        for(unsigned note=0;note<3;note++){
            double t=(double)i/CA_CHIME_RATE-note*0.105;if(t<0||t>0.40)continue;
            double attack=t<0.008?t/0.008:1,release=(0.40-t)/0.40;
            double phase=t*notes[note];phase-=floor(phase);
            value+=(1-4*fabs(phase-0.5))*attack*release*release*0.095;
        }
        samples[i]=(int16_t)(value*32767.0);
    }
    return true;
}
