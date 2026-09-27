// Exercise a live xdg_popup text-input surface, including explicit disable/enable.
#define _GNU_SOURCE
#include <wayland-client.h>
#include "xdg-shell.h"
#include "text-input.h"
#include <sys/mman.h>
#include <unistd.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct xdg_wm_base *wm;
static struct zwp_text_input_manager_v3 *manager;
static struct zwp_text_input_v3 *input;
static struct wl_surface *root,*menu;
static struct xdg_surface *root_xdg,*menu_xdg;
static struct wl_buffer *buffer;
static int bogus,released;
static void enable(void){zwp_text_input_v3_enable(input);zwp_text_input_v3_set_cursor_rectangle(input,20,20,2,20);zwp_text_input_v3_commit(input);puts("enabled-popup-input");}
static void ti_enter(void*d,struct zwp_text_input_v3*t,struct wl_surface*s){if(s==menu)enable();}
static void ti_leave(void*d,struct zwp_text_input_v3*t,struct wl_surface*s){}
static void preedit(void*d,struct zwp_text_input_v3*t,const char*s,int32_t a,int32_t b){}
static void commit(void*d,struct zwp_text_input_v3*t,const char*s){}
static void del(void*d,struct zwp_text_input_v3*t,uint32_t a,uint32_t b){}
static void done(void*d,struct zwp_text_input_v3*t,uint32_t s){}
static const struct zwp_text_input_v3_listener ti={ti_enter,ti_leave,preedit,commit,del,done};
static void configured(void*d,struct xdg_surface*s,uint32_t serial){xdg_surface_ack_configure(s,serial);struct wl_surface*w=d;wl_surface_attach(w,buffer,0,0);wl_surface_damage(w,0,0,400,300);wl_surface_commit(w);}
static const struct xdg_surface_listener config={configured};
static void popup_config(void*d,struct xdg_popup*p,int32_t x,int32_t y,int32_t w,int32_t h){}
static void popup_done(void*d,struct xdg_popup*p){puts("popup-done");}
static const struct xdg_popup_listener popup_events={.configure=popup_config,.popup_done=popup_done};
static void pe(void*d,struct wl_pointer*p,uint32_t n,struct wl_surface*s,wl_fixed_t x,wl_fixed_t y){}
static void pl(void*d,struct wl_pointer*p,uint32_t n,struct wl_surface*s){}
static void pm(void*d,struct wl_pointer*p,uint32_t t,wl_fixed_t x,wl_fixed_t y){}
static void pb(void*d,struct wl_pointer*p,uint32_t n,uint32_t t,uint32_t b,uint32_t state){
 if(menu||state!=(released?0:1))return;
 menu=wl_compositor_create_surface(compositor);menu_xdg=xdg_wm_base_get_xdg_surface(wm,menu);xdg_surface_add_listener(menu_xdg,&config,menu);
 struct xdg_positioner*pos=xdg_wm_base_create_positioner(wm);xdg_positioner_set_size(pos,400,300);xdg_positioner_set_anchor_rect(pos,50,50,1,1);xdg_positioner_set_anchor(pos,XDG_POSITIONER_ANCHOR_TOP_LEFT);xdg_positioner_set_gravity(pos,XDG_POSITIONER_GRAVITY_BOTTOM_RIGHT);
 struct xdg_popup*popup=xdg_surface_get_popup(menu_xdg,root_xdg,pos);xdg_popup_add_listener(popup,&popup_events,NULL);xdg_popup_grab(popup,seat,bogus?n+12345:n);wl_surface_commit(menu);puts("popup-requested");
}
static void pa(void*d,struct wl_pointer*p,uint32_t t,uint32_t a,wl_fixed_t v){}
static const struct wl_pointer_listener pointer={.enter=pe,.leave=pl,.motion=pm,.button=pb,.axis=pa};
static void caps(void*d,struct wl_seat*s,uint32_t c){if(c&WL_SEAT_CAPABILITY_POINTER)wl_pointer_add_listener(wl_seat_get_pointer(s),&pointer,NULL);}
static void name(void*d,struct wl_seat*s,const char*n){}
static const struct wl_seat_listener seats={caps,name};
static void ping(void*d,struct xdg_wm_base*w,uint32_t s){xdg_wm_base_pong(w,s);}
static const struct xdg_wm_base_listener wms={ping};
static void global(void*d,struct wl_registry*r,uint32_t id,const char*i,uint32_t v){
 if(!strcmp(i,"wl_compositor"))compositor=wl_registry_bind(r,id,&wl_compositor_interface,4);
 else if(!strcmp(i,"wl_shm"))shm=wl_registry_bind(r,id,&wl_shm_interface,1);
 else if(!strcmp(i,"xdg_wm_base")){wm=wl_registry_bind(r,id,&xdg_wm_base_interface,1);xdg_wm_base_add_listener(wm,&wms,NULL);}
 else if(!strcmp(i,"wl_seat")){seat=wl_registry_bind(r,id,&wl_seat_interface,4);wl_seat_add_listener(seat,&seats,NULL);}
 else if(!strcmp(i,"zwp_text_input_manager_v3"))manager=wl_registry_bind(r,id,&zwp_text_input_manager_v3_interface,1);
}
static void removed(void*d,struct wl_registry*r,uint32_t id){}
static const struct wl_registry_listener globals={global,removed};
static void top_config(void*d,struct xdg_toplevel*t,int32_t w,int32_t h,struct wl_array*s){}
static void top_close(void*d,struct xdg_toplevel*t){exit(0);}
static const struct xdg_toplevel_listener top={.configure=top_config,.close=top_close};
int main(int argc,char**argv){
 setbuf(stdout,NULL);bogus=argc>1&&!strcmp(argv[1],"bogus");released=argc>1&&!strcmp(argv[1],"released");display=wl_display_connect(NULL);if(!display)return 1;
 wl_registry_add_listener(wl_display_get_registry(display),&globals,NULL);wl_display_roundtrip(display);if(!compositor||!shm||!wm||!seat||!manager)return 2;
 input=zwp_text_input_manager_v3_get_text_input(manager,seat);zwp_text_input_v3_add_listener(input,&ti,NULL);
 int fd=memfd_create("forge-popup",MFD_CLOEXEC);if(fd<0||ftruncate(fd,400*300*4))return 3;uint32_t*data=mmap(NULL,400*300*4,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(data==MAP_FAILED)return 4;for(int i=0;i<400*300;i++)data[i]=0xffffffff;
 struct wl_shm_pool*pool=wl_shm_create_pool(shm,fd,400*300*4);buffer=wl_shm_pool_create_buffer(pool,0,400,300,400*4,WL_SHM_FORMAT_XRGB8888);close(fd);
 root=wl_compositor_create_surface(compositor);root_xdg=xdg_wm_base_get_xdg_surface(wm,root);xdg_surface_add_listener(root_xdg,&config,root);struct xdg_toplevel*t=xdg_surface_get_toplevel(root_xdg);xdg_toplevel_add_listener(t,&top,NULL);xdg_toplevel_set_title(t,"Forge popup input fixture");wl_surface_commit(root);
 for(;;){wl_display_dispatch_pending(display);wl_display_flush(display);struct pollfd fds[2]={{wl_display_get_fd(display),POLLIN,0},{0,POLLIN,0}};if(poll(fds,2,-1)<0)return 5;if(fds[0].revents&POLLIN)if(wl_display_dispatch(display)<0)return 6;if(fds[1].revents&POLLIN){char c;if(read(0,&c,1)!=1)return 0;if(c=='d'){zwp_text_input_v3_disable(input);zwp_text_input_v3_commit(input);puts("disabled-popup-input");}if(c=='e')enable();}}
}

