// Real Wayland fixture: retain the xdg_toplevel while attaching a NULL buffer.
#define _GNU_SOURCE
#include <wayland-client.h>
#include "xdg-shell.h"
#include <sys/mman.h>
#include <unistd.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct xdg_wm_base *wm;
static struct wl_surface *surface;
static struct wl_buffer *buffer;
static struct xdg_surface *xdg;
static int visible=1;
static struct wl_output *outputs[4];static int output_count;
static void keymap(void*d,struct wl_keyboard*k,uint32_t f,int fd,uint32_t s){close(fd);}
static void enter(void*d,struct wl_keyboard*k,uint32_t n,struct wl_surface*s,struct wl_array*a){puts("keyboard-enter");}
static void leave(void*d,struct wl_keyboard*k,uint32_t n,struct wl_surface*s){puts("keyboard-leave");}
static void key(void*d,struct wl_keyboard*k,uint32_t n,uint32_t t,uint32_t c,uint32_t s){printf("key:%u:%u\n",c,s);}
static void mods(void*d,struct wl_keyboard*k,uint32_t n,uint32_t dep,uint32_t lat,uint32_t lock,uint32_t group){printf("modifiers:%u\n",dep);}
static void repeat(void*d,struct wl_keyboard*k,int32_t rate,int32_t delay){}
static const struct wl_keyboard_listener keys={keymap,enter,leave,key,mods,repeat};
static void pe(void*d,struct wl_pointer*p,uint32_t n,struct wl_surface*s,wl_fixed_t x,wl_fixed_t y){puts("pointer-enter");}
static void pl(void*d,struct wl_pointer*p,uint32_t n,struct wl_surface*s){puts("pointer-leave");}
static void pm(void*d,struct wl_pointer*p,uint32_t t,wl_fixed_t x,wl_fixed_t y){}
static void pb(void*d,struct wl_pointer*p,uint32_t n,uint32_t t,uint32_t b,uint32_t s){printf("button:%u:%u\n",b,s);}
static void pa(void*d,struct wl_pointer*p,uint32_t t,uint32_t a,wl_fixed_t v){printf("axis:%u\n",a);}
static const struct wl_pointer_listener pointer={.enter=pe,.leave=pl,.motion=pm,.button=pb,.axis=pa};
static void caps(void*d,struct wl_seat*s,uint32_t c){
 if(c&WL_SEAT_CAPABILITY_KEYBOARD)wl_keyboard_add_listener(wl_seat_get_keyboard(s),&keys,NULL);
 if(c&WL_SEAT_CAPABILITY_POINTER)wl_pointer_add_listener(wl_seat_get_pointer(s),&pointer,NULL);
}
static void name(void*d,struct wl_seat*s,const char*n){}
static const struct wl_seat_listener seat={caps,name};
static void ping(void*d,struct xdg_wm_base*w,uint32_t s){xdg_wm_base_pong(w,s);}
static const struct xdg_wm_base_listener wm_listener={ping};
static void global(void*d,struct wl_registry*r,uint32_t id,const char*i,uint32_t v){
 if(!strcmp(i,"wl_compositor"))compositor=wl_registry_bind(r,id,&wl_compositor_interface,4);
 else if(!strcmp(i,"wl_output")&&output_count<4)outputs[output_count++]=wl_registry_bind(r,id,&wl_output_interface,1);
 else if(!strcmp(i,"wl_shm"))shm=wl_registry_bind(r,id,&wl_shm_interface,1);
 else if(!strcmp(i,"xdg_wm_base")){wm=wl_registry_bind(r,id,&xdg_wm_base_interface,1);xdg_wm_base_add_listener(wm,&wm_listener,NULL);}
 else if(!strcmp(i,"wl_seat")){struct wl_seat*s=wl_registry_bind(r,id,&wl_seat_interface,4);wl_seat_add_listener(s,&seat,NULL);}
}
static void removed(void*d,struct wl_registry*r,uint32_t id){}
static const struct wl_registry_listener registry={global,removed};
static void draw(void){wl_surface_attach(surface,buffer,0,0);wl_surface_damage(surface,0,0,1280,800);wl_surface_commit(surface);}
static void configured(void*d,struct xdg_surface*s,uint32_t serial){xdg_surface_ack_configure(s,serial);if(visible)draw();}
static const struct xdg_surface_listener config={configured};
static void top_config(void*d,struct xdg_toplevel*t,int32_t w,int32_t h,struct wl_array*s){}
static void top_close(void*d,struct xdg_toplevel*t){exit(0);}
static const struct xdg_toplevel_listener top={.configure=top_config,.close=top_close};
int main(int argc,char **argv){
 setbuf(stdout,NULL);display=wl_display_connect(NULL);if(!display)return 1;
 struct wl_registry*r=wl_display_get_registry(display);wl_registry_add_listener(r,&registry,NULL);wl_display_roundtrip(display);
 if(!compositor||!shm||!wm)return 2;
 int fd=memfd_create("forge-lifecycle",MFD_CLOEXEC);if(fd<0||ftruncate(fd,1280*800*4))return 3;
 uint32_t*data=mmap(NULL,1280*800*4,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(data==MAP_FAILED)return 4;
 for(int i=0;i<1280*800;i++)data[i]=0xffaa33cc;
 struct wl_shm_pool*pool=wl_shm_create_pool(shm,fd,1280*800*4);buffer=wl_shm_pool_create_buffer(pool,0,1280,800,1280*4,WL_SHM_FORMAT_XRGB8888);close(fd);
 surface=wl_compositor_create_surface(compositor);xdg=xdg_wm_base_get_xdg_surface(wm,surface);xdg_surface_add_listener(xdg,&config,NULL);
 struct xdg_toplevel*t=xdg_surface_get_toplevel(xdg);xdg_toplevel_add_listener(t,&top,NULL);xdg_toplevel_set_title(t,"Forge lifecycle fixture");if(argc!=2||atoi(argv[1])>=output_count)return 7;xdg_toplevel_set_fullscreen(t,outputs[atoi(argv[1])]);wl_surface_commit(surface);wl_display_roundtrip(display);puts("fullscreen-ready");
 for(;;){
  wl_display_dispatch_pending(display);wl_display_flush(display);
  struct pollfd fds[2]={{wl_display_get_fd(display),POLLIN,0},{0,POLLIN,0}};
  if(poll(fds,2,-1)<0)return 5;
  if(fds[0].revents&POLLIN)if(wl_display_dispatch(display)<0)return 6;
  if(fds[1].revents&POLLIN){char c;if(read(0,&c,1)!=1)return 0;
   if(c=='m'){visible=1;wl_surface_commit(surface);wl_display_roundtrip(display);draw();puts("mapped");}
   if(c=='u'){visible=0;wl_surface_attach(surface,NULL,0,0);wl_surface_commit(surface);puts("unmapped");}
  }
 }
}

