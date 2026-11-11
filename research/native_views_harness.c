#define guest_main unused_debug_v1_tests
#include "native_debug_harness.c"
#undef guest_main
extern int a7_fl_views_test_run(void);
extern const void *a7_fl_views_test_report(void);
static unsigned *vm=(void*)VM,*table0=(void*)(VM+0x100),*table1=(void*)(VM+0x200);
static void views_setup(void){
 setup();vm[0]=2;vm[8]=VM+0x100;vm[9]=VM+0x200;
 zero(VM+0x100,0x400);
 table0[1]=VM+0x300;table0[5]=VM+0x400;
 table1[1]=VM+0x400;table1[5]=0;
 ((unsigned*)(VM+0x300))[0]=VB+0x87a9c8;((unsigned*)(VM+0x300))[9]=VM;
 ((unsigned*)(VM+0x400))[0]=VB+0x87b600;((unsigned*)(VM+0x400))[9]=VM;
}
void guest_main(void){
 views_setup();check(a7_fl_views_test_run()==1,"bounded views traversal");const unsigned*r=a7_fl_views_test_report();
 check(r[0]==0x41374656&&r[1]==1&&r[2]==97492&&r[4]==2&&r[5]==VM+0x100&&r[6]==VM+0x200&&r[7]==4,"views report ABI");
 const unsigned*records=r+(32+66740)/4;
 check(records[0]==15&&records[15]==23&&records[30]==23&&records[45]==1,"Global/Setting/null classification without methods");
 check(records[2]==VM+0x300&&records[17]==VM+0x400,"actual slot pointers captured");
 check(vm[0]==2&&table0[1]==VM+0x300&&((unsigned*)(VM+0x300))[0]==VB+0x87a9c8,"view graph unchanged");
 views_setup();((unsigned*)(VM+0x400))[9]=VM+4;check(a7_fl_views_test_run()==1,"wrong owner still read-only");records=(const unsigned*)a7_fl_views_test_report()+(32+66740)/4;check(records[15]==19,"owner mismatch distinct");
 views_setup();table0[1]=0x33000000;check(a7_fl_views_test_run()==1,"foreign object rejected without dereference");records=(const unsigned*)a7_fl_views_test_report()+(32+66740)/4;check(records[0]==1,"only valid slot read");
 views_setup();vm[0]=257;check(a7_fl_views_test_run()==-31,"slot bound enforced");
 views_setup();vm[0]=0;check(a7_fl_views_test_run()==-31,"empty table diagnosed");
 views_setup();vm[8]=0xfffffff0;check(a7_fl_views_test_run()==-32,"overflow table rejected");r=a7_fl_views_test_report();check(r[7]==2,"other bounded table retained");
 views_setup();vm[9]=VM+0x201;check(a7_fl_views_test_run()==-32,"misaligned table rejected");
 check(opens==7&&syms==14&&closes==7,"all refs balanced");
 put("NATIVE_VIEWS_PASSED checks=");number(checks);put("; bounded two-table traversal, object/owner/type guards, no mutations\n");finish();
}
