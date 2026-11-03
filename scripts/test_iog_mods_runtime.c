/* ROM-free integration fixture. Includes the ACTUAL iog_mods implementation;
 * only its host services and source-fingerprint decision are injected. */
#define IogCheatRateSourceSupported TestSourceSupported
#include "../src/iog_mods.c"
#undef IogCheatRateSourceSupported

static uint8_t test_ram[0x20000],test_rom[0x200000],expected_ram[0x20000];
static Cart test_cart={test_rom,sizeof test_rom};
static Snes test_snes={test_ram,&test_cart,0};
Snes *g_snes=&test_snes;
static uint64_t generation=1;
static bool source_supported=true,randomizer,apocalypse;
static unsigned assertions,source_checks,persist_calls;
static SNESModActivationCallback reset_callback;
static SNESModFrameCallback frame_callbacks[16];
static unsigned frame_count;
static struct {const char*id;SNESModActivationCallback fn;} plugins[16];
static unsigned plugin_count;
static int configured_multiplier=1;
static int configured_dp=-1,configured_str=-1,configured_def=-1,configured_hp=-1;
static const char *configured_run_button="Y";
static char persisted_feature[40],persisted_option[40],persisted_value[40];
static int persisted_enabled;
#define CHECK(v) do {assertions++;if(!(v)){fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#v);exit(1);}}while(0)

uint64_t RtlStateGeneration(void){return generation;}
bool IogRandomizerActive(void){return randomizer;}
bool TestSourceSupported(const uint8_t*rom,size_t size)
{source_checks++;CHECK(rom==test_rom&&size==sizeof test_rom);return source_supported;}
int snes_mod_register_reset_callback(SNESModActivationCallback fn){reset_callback=fn;return 1;}
int snes_mod_register_activation_plugin(const char*id,SNESModActivationCallback fn)
{CHECK(plugin_count<16);plugins[plugin_count].id=id;plugins[plugin_count++].fn=fn;return 1;}
int snes_mod_register_presentation_plugin(const char*id,SNESModActivationCallback fn)
{return snes_mod_register_activation_plugin(id,fn);}
int snes_mod_register_frame_callback(SNESModFrameCallback fn)
{CHECK(frame_count<16);frame_callbacks[frame_count++]=fn;return 1;}
int snes_mod_register_input_filter(SNESModInputFilter fn){(void)fn;return 1;}
int snes_mod_runtime_feature_enabled_c(const char*pkg,const char*feature)
{return !strcmp(pkg,"iog.apocalypse")&&!strcmp(feature,"apocalypse_gaia")&&apocalypse;}
int snes_mod_runtime_feature_option_value_c(const char*pkg,const char*feature,const char*option,char*out,size_t cap)
{
    if(!strcmp(pkg,"iog.cheats")&&!strcmp(feature,"room_rewards")&&!strcmp(option,"multiplier"))
        return snprintf(out,cap,"%d",configured_multiplier)>0;
    int value=-1;
    if(!strcmp(pkg,"iog.cheats")) {
        if(!strcmp(feature,"dp")&&!strcmp(option,"amount"))value=configured_dp;
        if(!strcmp(feature,"stats")) {
            if(!strcmp(option,"strength"))value=configured_str;
            if(!strcmp(option,"defense"))value=configured_def;
            if(!strcmp(option,"max_hp"))value=configured_hp;
        }
    }
    if(value>=0)return snprintf(out,cap,"%d",value)>0;
    if(!strcmp(pkg,"iog.enhancements")&&!strcmp(feature,"run")&&!strcmp(option,"button"))
        return snprintf(out,cap,"%s",configured_run_button)>0;
    if(cap)out[0]=0;return 0;
}
int snes_mod_runtime_persist_feature_c(const char*pkg,const char*feature,int enabled,const char*option,const char*value)
{
    CHECK(!strcmp(pkg,"iog.cheats"));persist_calls++;
    snprintf(persisted_feature,sizeof persisted_feature,"%s",feature);
    snprintf(persisted_option,sizeof persisted_option,"%s",option?option:"");
    snprintf(persisted_value,sizeof persisted_value,"%s",value?value:"");persisted_enabled=enabled;
    return 1;
}
void PresentFilter_Set(int value){(void)value;}
void SnesRa_SetBlocked(const char*why){(void)why;}
static void tick(void){for(unsigned i=0;i<frame_count;i++)frame_callbacks[i]();}
static void activate(const char*id)
{for(unsigned i=0;i<plugin_count;i++)if(!strcmp(id,plugins[i].id)){plugins[i].fn();return;}CHECK(false);}
static void reset_fixture(unsigned reward)
{
    memset(test_ram,0,sizeof test_ram);memset(test_rom,0,sizeof test_rom);
    g_snes=&test_snes;generation++;source_supported=true;randomizer=apocalypse=false;
    frame_count=0;CHECK(reset_callback!=NULL);reset_callback();CHECK(frame_count==4);
    Wr(0x0644,0x10);Wr(0x09AA,0x1000);Wr(0x0ACE,5);Wr(0x0ACA,8);Wr(0x0ADE,4);Wr(0x0ADC,3);
    test_rom[0x01AADE + 0x10]=(uint8_t)reward;
}
static void original_reward(unsigned kind)
{
    static const unsigned addresses[]={0x0ACA,0x0ADE,0x0ADC};
    test_ram[0x0A62]|=1;Wr(addresses[kind-1],Rd(addresses[kind-1])+1);
}
static void expect_extra(unsigned kind,unsigned extra)
{
    static const unsigned addresses[]={0x0ACA,0x0ADE,0x0ADC};
    memcpy(expected_ram,test_ram,sizeof expected_ram);
    unsigned address=addresses[kind-1],value=Rd(address)+extra;
    expected_ram[address]=(uint8_t)value;expected_ram[address+1]=(uint8_t)(value>>8);
    if(kind==1){value=Rd(0x0ACE)+extra;expected_ram[0x0ACE]=(uint8_t)value;expected_ram[0x0ACF]=(uint8_t)(value>>8);}
    tick();CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
}
static void reward_suite(void)
{
    reset_fixture(1);CHECK(IogRoomRewardMultiplierGet()==1);CHECK(!IogCheatsSessionTainted());
    tick();original_reward(1);memcpy(expected_ram,test_ram,sizeof test_ram);tick();
    CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));CHECK(!source_checks);CHECK(!IogCheatsSessionTainted());
    for(unsigned kind=1;kind<=3;kind++)for(int multiplier=2;multiplier<=8;multiplier++){
        reset_fixture(kind);IogRoomRewardMultiplierSet(multiplier);
        CHECK(IogRoomRewardMultiplierGet()==multiplier);CHECK(persisted_enabled==1);
        CHECK(!strcmp(persisted_feature,"room_rewards")&&!strcmp(persisted_option,"multiplier"));
        tick();original_reward(kind);expect_extra(kind,(unsigned)multiplier-1);
        memcpy(expected_ram,test_ram,sizeof test_ram);tick();CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
    }
    /* Shared native option activation uses the actual plugin, not only setter. */
    reset_fixture(2);configured_multiplier=6;activate("iog.cheat.room_rewards");
    CHECK(IogRoomRewardMultiplierGet()==6);tick();original_reward(2);expect_extra(2,5);
    IogRoomRewardMultiplierSet(1);CHECK(!persisted_enabled&&!strcmp(persisted_value,"1"));
    CHECK(IogCheatsSessionTainted());
    /* A load/generation change can never turn an already-set flag into a gain. */
    reset_fixture(2);IogRoomRewardMultiplierSet(8);tick();original_reward(2);generation++;
    memcpy(expected_ram,test_ram,sizeof test_ram);tick();CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
    /* A real reset/load hook invalidates a pending flag observation. */
    reset_fixture(2);IogRoomRewardMultiplierSet(8);tick();test_ram[0x0A62]|=1;tick();
    IogCheatRatesInvalidate();Wr(0x0ADE,Rd(0x0ADE)+1);
    memcpy(expected_ram,test_ram,sizeof test_ram);tick();CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
    /* Original reward after the flag's scheduling boundary is recognized. */
    reset_fixture(3);IogRoomRewardMultiplierSet(4);tick();test_ram[0x0A62]|=1;tick();
    Wr(0x0ADC,Rd(0x0ADC)+1);expect_extra(3,3);
    for(unsigned block=0;block<7;block++){
        reset_fixture(2);IogRoomRewardMultiplierSet(8);tick();
        if(block==0)randomizer=true;
        if(block==1)apocalypse=true;
        if(block==2)test_ram[0x0B54]=1;
        if(block==3)IogCheatSet(2,1);
        if(block==4)source_supported=false;
        if(block==5)Wr(0x09AA,0);
        if(block==6)Wr(0x0ACE,0);
        original_reward(2);memcpy(expected_ram,test_ram,sizeof test_ram);tick();
        CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
    }
    reset_fixture(1);IogRoomRewardMultiplierSet(8);tick();g_snes=NULL;tick();g_snes=&test_snes;
    original_reward(1);memcpy(expected_ram,test_ram,sizeof test_ram);tick();CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
    CHECK(persist_calls>0);
}
static void taint_suite(const char*which)
{
    reset_fixture(1);CHECK(!IogCheatsSessionTainted());
    if(!strcmp(which,"taint-hp"))activate("iog.cheat.hp");
    else if(!strcmp(which,"taint-dp"))activate("iog.cheat.dp");
    else if(!strcmp(which,"taint-stats"))activate("iog.cheat.stats");
    else if(!strcmp(which,"taint-room")){configured_multiplier=8;activate("iog.cheat.room_rewards");}
    else if(!strcmp(which,"taint-toggle"))IogCheatSet(0,1);
    else if(!strcmp(which,"taint-api"))IogCheatsMarkUsed();
    else CHECK(false);
    CHECK(IogCheatsSessionTainted());
    IogRoomRewardMultiplierSet(1);for(int i=0;i<3;i++)IogCheatSet(i,0);
    CHECK(IogCheatsSessionTainted());IogCheatRatesInvalidate();CHECK(IogCheatsSessionTainted());
    reset_fixture(1);CHECK(IogCheatsSessionTainted());generation++;tick();CHECK(IogCheatsSessionTainted());
}
static void live_cheat_suite(void)
{
    reset_fixture(1);
    configured_str=20;configured_def=18;configured_hp=30;
    CHECK(!IogCheatGet(2));IogCheatSet(2,1);tick();
    CHECK(Rd(0x0ADE)==20&&Rd(0x0ADC)==18&&Rd(0x0ACA)==30&&Rd(0x0ACE)==30);
    CHECK(!strcmp(persisted_feature,"stats")&&persisted_enabled&&IogCheatsSessionTainted());
    IogCheatSet(2,0);Wr(0x0ADE,4);Wr(0x0ADC,3);Wr(0x0ACA,8);Wr(0x0ACE,5);tick();
    CHECK(Rd(0x0ADE)==4&&Rd(0x0ADC)==3&&Rd(0x0ACA)==8&&Rd(0x0ACE)==5);
    configured_str=25;configured_def=0;configured_hp=0;IogCheatSet(2,1);tick();
    CHECK(Rd(0x0ADE)==25&&Rd(0x0ADC)==3&&Rd(0x0ACA)==8&&Rd(0x0ACE)==5);
    configured_str=0;IogCheatSet(2,0);IogCheatSet(2,1);Wr(0x0ADE,4);tick();
    CHECK(Rd(0x0ADE)==4);IogCheatSet(2,0);
    configured_dp=321;IogCheatSet(1,1);tick();CHECK(Rd(0x0AD6)==321);
    CHECK(!strcmp(persisted_feature,"dp")&&persisted_enabled);
    IogCheatSet(1,0);Wr(0x0AD6,7);tick();CHECK(Rd(0x0AD6)==7);
    configured_dp=654;IogCheatSet(1,1);tick();CHECK(Rd(0x0AD6)==654);
    configured_dp=0;IogCheatSet(1,0);IogCheatSet(1,1);Wr(0x0AD6,7);tick();CHECK(Rd(0x0AD6)==7);
    IogCheatSet(1,0);IogCheatSet(0,1);tick();CHECK(Rd(0x0ACE)==8);
    Wr(0x0ACE,0);tick();CHECK(Rd(0x0ACE)==0); /* No revive or lethal-hit prevention. */
    IogCheatSet(0,0);Wr(0x0ACE,5);tick();CHECK(Rd(0x0ACE)==5);
    configured_str=configured_def=configured_hp=0;activate("iog.cheat.stats");tick();
    CHECK(Rd(0x0ADE)==4&&Rd(0x0ADC)==3&&Rd(0x0ACA)==8&&Rd(0x0ACE)==5);
    IogCheatSet(2,0);CHECK(IogCheatsSessionTainted());
}
static void run_suite(void)
{
    static const char*buttons[]={"Y","X","L","R"};
    static const unsigned masks[]={kPadY,kPadX,kPadL,kPadR};
    static const unsigned directions[]={kPadRight,kPadLeft,kPadDown,kPadUp};
    for(unsigned b=0;b<4;b++)for(unsigned d=0;d<4;d++) {
        reset_fixture(1);configured_run_button=buttons[b];activate("iog.run");CHECK(frame_count==5);
        test_snes.input1_currentState=masks[b]|directions[d];Wr(0x09B8,17);tick();
        CHECK(Rd(d<2?0x09B2:0x09B4)==(d&1?0xFFFD:3));CHECK(Rd(0x09B8)==0);
        CHECK(Rd(d<2?0x09B4:0x09B2)==0);
    }
    for(unsigned gate=0;gate<8;gate++) {
        reset_fixture(1);configured_run_button="Y";activate("iog.run");
        test_snes.input1_currentState=kPadY|kPadRight;
        if(gate==0)Wr(0x09AA,0);
        if(gate==1)Wr(0x09AE,0x0800);
        if(gate==2)Wr(0x09AE,0x1000);
        if(gate==3)Wr(0x09AE,0x2000);
        if(gate==4)test_snes.input1_currentState=kPadY;
        if(gate==5)test_snes.input1_currentState=kPadRight;
        if(gate==6)Wr(0x0644,0x00FF);
        if(gate==7)Wr(0x09EC,0x2001);
        memcpy(expected_ram,test_ram,sizeof expected_ram);tick();CHECK(!memcmp(expected_ram,test_ram,sizeof test_ram));
    }
    reset_fixture(1);test_snes.input1_currentState=kPadY|kPadRight;tick();CHECK(!Rd(0x09B2));
    /* High scene IDs include real Dark Castoth gameplay: never blanket-gate. */
    reset_fixture(1);configured_run_button="Y";activate("iog.run");Wr(0x0644,0x00F2);
    test_snes.input1_currentState=kPadY|kPadRight;tick();CHECK(Rd(0x09B2)==3);
}
int main(int argc,char**argv)
{
    CHECK(argc==2);register_iog_mods();CHECK(plugin_count==8);
    if(!strcmp(argv[1],"rewards"))reward_suite();
    else if(!strcmp(argv[1],"live-cheats"))live_cheat_suite();
    else if(!strcmp(argv[1],"run"))run_suite();
    else taint_suite(argv[1]);
    printf("PASS %u actual iog_mods callback integration assertions: %s; ROM-free host/source-gate stubs\n",assertions,argv[1]);
    return 0;
}
