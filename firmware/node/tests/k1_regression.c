/* Exercise the actual state machine against deterministic failed peripherals. */
#define main pg_original_host_main
#include "../host_sim.c"
#undef main
#include <assert.h>
#ifdef _WIN32
#include <stdlib.h>
#endif

int main(void) {
    pg_node_t n;
    static const char *joints[]={"C06-L1-PABUC","C06-L2-PABUC","C06-L3-PABUC","C07-L1-PABUC","C07-L2-PABUC","C07-L3-PABUC"};
    int k;
#ifdef _WIN32
    _set_error_mode(_OUT_TO_STDERR);
#endif
    /* The fitted OPA333 and awake FRAM alone exceed the legacy 3 uA budget. */
    if (pg_pwr_table[PG_PWR_SLEEP].ua<37u) {
        puts("FAIL: legacy sleep budget omits fitted analog/FRAM loads");
        return 1;
    }
    for(k=1;k<=6;k++) {
        pg_node_init(&n,(uint16_t)(0x100+k),400);
        assert(n.device[4]=='0'+k);
        assert(strcmp(n.joint,joints[k-1])==0);
    }
    memset(&VP,0,sizeof VP);
    VP.vbat_mv=3600; VP.mount_ok=1; VP.t_joint[0]=3200; VP.ct_fault=1;
    pg_node_init(&n,0x0104,400);
    assert(strcmp(n.device,"TC-04")==0);
    assert(strcmp(n.joint,"C07-L1-PABUC")==0);
    n.state=PG_ST_SAMPLE;
    pg_node_step(&n);
    assert(n.state!=PG_ST_DE_ENERGISED);
    assert(n.flags&PG_F_SENSOR_FAULT);
    VP.ct_fault=0;
    n.state=PG_ST_SAMPLE;
    pg_node_step(&n);
    assert(n.state==PG_ST_DE_ENERGISED);
    if (n.flags&PG_F_SENSOR_FAULT) {
        puts("FAIL: valid zero-current recovery retained SENSOR_FAULT");
        return 1;
    }
    puts("K1 identity and invalid-CT negative controls: PASS");
    return 0;
}
