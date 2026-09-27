#include <wayland-client.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct output { struct wl_output *object; int x,y,w,h,scale; char name[80]; } outputs[16];
static int count;
static void geometry(void *d, struct wl_output *o, int x,int y,int pw,int ph,int sub,const char *make,const char *model,int transform) {
 (void)o;(void)pw;(void)ph;(void)sub;(void)make;(void)model;(void)transform; struct output *v=d;v->x=x;v->y=y;
}
static void mode(void *d,struct wl_output *o,uint32_t flags,int w,int h,int refresh) {
 (void)o;(void)refresh;if(flags&WL_OUTPUT_MODE_CURRENT){struct output *v=d;v->w=w;v->h=h;}
}
static void done(void *d,struct wl_output *o){(void)d;(void)o;}
static void scale(void *d,struct wl_output *o,int s){(void)o;((struct output*)d)->scale=s;}
static void name(void *d,struct wl_output *o,const char *s){(void)o;snprintf(((struct output*)d)->name,80,"%s",s);}
static void description(void *d,struct wl_output *o,const char *s){(void)d;(void)o;(void)s;}
static const struct wl_output_listener listener={geometry,mode,done,scale,name,description};
static void global(void *d,struct wl_registry *r,uint32_t id,const char *interface,uint32_t version){
 (void)d;if(strcmp(interface,"wl_output")||count>=16)return;
 struct output *o=&outputs[count++];o->scale=1;
 o->object=wl_registry_bind(r,id,&wl_output_interface,version<4?version:4);
 wl_output_add_listener(o->object,&listener,o);
}
static void removed(void*d,struct wl_registry*r,uint32_t id){(void)d;(void)r;(void)id;}
int main(int argc,char **argv){
 struct wl_display *display=wl_display_connect(NULL);if(!display)return 2;
 struct wl_registry *registry=wl_display_get_registry(display);
 const struct wl_registry_listener globals={global,removed};wl_registry_add_listener(registry,&globals,NULL);
 for(int i=0;i<3;i++)if(wl_display_roundtrip(display)<0)return 3;
 for(int i=0;i<count;i++)printf("output:%s:%d,%d:%dx%d:scale=%d\n",outputs[i].name,outputs[i].x,outputs[i].y,outputs[i].w,outputs[i].h,outputs[i].scale);
 printf("outputs:%d\n",count);
 for(int i=0;i<count;i++)wl_output_destroy(outputs[i].object);
 wl_registry_destroy(registry);wl_display_disconnect(display);
 return argc==2&&count!=atoi(argv[1])?1:0;
}
