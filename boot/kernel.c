#include "rv32.h"
#include "module.h"
static RV vm;static RVFS fs;static RVFds fds;static uint8_t ram[RV_SIZE];
extern const uint8_t app_start[],app_end[],file_start[],file_end[],kernel_end[];
static const uint8_t *external_image;static uint32_t external_size;
static void out(uint16_t p,uint8_t b){__asm__ volatile("outb %0,%1"::"a"(b),"Nd"(p));}
static uint8_t in(uint16_t p){uint8_t b;__asm__ volatile("inb %1,%0":"=a"(b):"Nd"(p));return b;}
static void serial_init(void){out(0x3f9,0);out(0x3fb,0x80);out(0x3f8,1);out(0x3f9,0);out(0x3fb,3);out(0x3fa,0xc7);out(0x3fc,3);}
static void tx(uint8_t b){while(!(in(0x3fd)&0x20)){}out(0x3f8,b);}
static uint8_t rx(void){while(!(in(0x3fd)&1)){}return in(0x3f8);}
static void print(const char *s){while(*s)tx((uint8_t)*s++);}
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int32_t stream(void *ctx,int output,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;(void)fd;if(!n)return 0;if(output){for(uint32_t i=0;i<n;i++)tx(buf[i]);return (int32_t)n;}buf[0]=rx();return 1;}
static void run(void){const char *args[]={"demo","kernel"};int r=rv_load(&vm,ram,app_start,(size_t)(app_end-app_start),2,args);fs_reset_fds(&fs,&fds);if(!r)r=rv_run(&vm,10000000,stream,0,&fs,&fds);if(r||vm.status)print("guest failed\r\n");else print("guest exited 0\r\n");}
static void file(void){const char *args[]={"file","count","counter"};int r=rv_load(&vm,ram,file_start,(size_t)(file_end-file_start),3,args);fs_reset_fds(&fs,&fds);if(!r)r=rv_run(&vm,10000000,stream,0,&fs,&fds);if(r||vm.status)print("file failed\r\n");}
static void module(const uint32_t *info){
    if(!info||!(info[0]&1u)||!(info[0]&8u))return;
    uint32_t top=mb_top(info[2]);
    if(!mb_range((uint32_t)(uintptr_t)info,28,top)||info[5]!=1||!mb_range(info[6],16,top)){print("module refused\r\n");return;}
    const uint32_t *m=(const uint32_t *)(uintptr_t)info[6];
    if(!mb_module(m[0],m[1],top,(uint32_t)(uintptr_t)kernel_end,RV_SIZE)){print("module refused\r\n");return;}
    external_image=(const uint8_t *)(uintptr_t)m[0];external_size=m[1]-m[0];print("external module available\r\n");
}
static void external(void){
    if(!external_image){print("no external module\r\n");return;}
    const char *args[]={"external","kernel"},*env[]={"MODE=vlk"};
    int r=rv_load_env(&vm,ram,external_image,external_size,2,args,1,env);fs_reset_fds(&fs,&fds);
    if(!r)r=rv_run(&vm,10000000,stream,0,&fs,&fds);
    if(r||vm.status)print("external failed\r\n");else print("external exited 0\r\n");
}
void kmain(uint32_t magic,const uint32_t *info){serial_init();if(magic!=0x2badb002){print("invalid boot\r\n");return;}print("VL-K bare metal\r\n");module(info);run();char line[32];unsigned n=0;print("vlk> ");for(;;){uint8_t c=rx();if(c=='\r'||c=='\n'){tx('\r');tx('\n');line[n]=0;if(eq(line,"run"))run();else if(eq(line,"file"))file();else if(eq(line,"external"))external();else if(eq(line,"help"))print("help run file external halt\r\n");else if(eq(line,"halt")){print("halted\r\n");return;}else if(n)print("unknown command\r\n");n=0;print("vlk> ");}else if(c==8||c==127){if(n){n--;print("\b \b");}}else if(c>=32&&c<127&&n<sizeof(line)-1){line[n++]=(char)c;tx(c);}}}
