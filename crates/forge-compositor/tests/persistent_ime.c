/* Protocol fixture: deliberately keeps a live popup across deactivate/activate.
 * Bound over /usr/bin/fcitx5 only inside the disposable nspawn mount namespace.
 * It cannot request privileged roles as an ordinary desktop application. */
#include <wayland-client.h>
#include "input-method.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct zwp_input_method_manager_v2 *manager;
static struct wl_surface *surface;
static struct wl_buffer *buffer;
static int active;
static void activated(void*d,struct zwp_input_method_v2*i){(void)d;(void)i;active=1;}
static void deactivated(void*d,struct zwp_input_method_v2*i){(void)d;(void)i;active=0;}
static void surrounding(void*d,struct zwp_input_method_v2*i,const char*t,uint32_t c,uint32_t a){(void)d;(void)i;(void)t;(void)c;(void)a;}
static void cause(void*d,struct zwp_input_method_v2*i,uint32_t c){(void)d;(void)i;(void)c;}
static void content(void*d,struct zwp_input_method_v2*i,uint32_t h,uint32_t p){(void)d;(void)i;(void)h;(void)p;}
static void done(void*d,struct zwp_input_method_v2*ime){
 (void)d;if(!active)return;
 if(!surface){
  surface=wl_compositor_create_surface(compositor);
  (void)zwp_input_method_v2_get_input_popup_surface(ime,surface);
  char path[]="/tmp/forge-ime-test-XXXXXX";int fd=mkstemp(path);unlink(path);
  if(fd<0||ftruncate(fd,40*20*4))exit(3);
  uint32_t*p=mmap(NULL,40*20*4,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(p==MAP_FAILED)exit(4);
  for(int n=0;n<40*20;n++)p[n]=getenv("FORGE_TEST_IME_ALPHA")?0x80008000:0xff00ff00;
  struct wl_shm_pool*pool=wl_shm_create_pool(shm,fd,40*20*4);
  buffer=wl_shm_pool_create_buffer(pool,0,40,20,40*4,WL_SHM_FORMAT_ARGB8888);
  wl_shm_pool_destroy(pool);munmap(p,40*20*4);close(fd);
 }
 wl_surface_attach(surface,buffer,0,0);wl_surface_damage(surface,0,0,40,20);wl_surface_commit(surface);
}
static void unavailable(void*d,struct zwp_input_method_v2*i){(void)d;(void)i;exit(5);}
static const struct zwp_input_method_v2_listener events={activated,deactivated,surrounding,cause,content,done,unavailable};
static void global(void*d,struct wl_registry*r,uint32_t id,const char*name,uint32_t version){
 (void)d;(void)version;
 if(!strcmp(name,"wl_compositor"))compositor=wl_registry_bind(r,id,&wl_compositor_interface,4);
 if(!strcmp(name,"wl_shm"))shm=wl_registry_bind(r,id,&wl_shm_interface,1);
 if(!strcmp(name,"wl_seat"))seat=wl_registry_bind(r,id,&wl_seat_interface,7);
 if(!strcmp(name,"zwp_input_method_manager_v2"))manager=wl_registry_bind(r,id,&zwp_input_method_manager_v2_interface,1);
}
static void removed(void*d,struct wl_registry*r,uint32_t id){(void)d;(void)r;(void)id;}
int main(void){
 struct wl_display*display=wl_display_connect(NULL);if(!display)return 1;
 struct wl_registry*r=wl_display_get_registry(display);
 const struct wl_registry_listener globals={global,removed};wl_registry_add_listener(r,&globals,NULL);
 if(wl_display_roundtrip(display)<0||!compositor||!shm||!seat||!manager)return 2;
 struct zwp_input_method_v2*ime=zwp_input_method_manager_v2_get_input_method(manager,seat);
 zwp_input_method_v2_add_listener(ime,&events,NULL);
 while(wl_display_dispatch(display)>=0){}
 return 0;
}
