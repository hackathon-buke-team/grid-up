/* Produce interoperability fixtures with the production C encoder. */
#define main pg_original_host_main
#include "../host_sim.c"
#undef main
#include <assert.h>
int main(void) {
    pg_frame_t f; uint8_t raw[PG_FRAME_MAX]; int i,j,len;
    memset(&f,0,sizeof f);
    f.msgtype=PG_MSG_DATA;f.boot=3;f.ts=1789900000u;f.seq=42;
    f.flags=PG_F_DATA_VALID;f.cadence=PG_CAD_WATCH;
    f.t_mean_lsb=45*128;f.t_min_lsb=44*128;f.t_max_lsb=46*128;
    f.theta_lsb=PG_THETA_INVALID;f.i_rms_ma=120500;f.vbat_mv=3560;
    f.rssi_dbm=-82;f.mcu_c=31;
    for(i=1;i<=6;i++) {
        f.node_id=(uint16_t)(0x100+i);len=pg_frame_encode(&f,raw,sizeof raw);assert(len==35);
        for(j=0;j<len;j++)printf("%02x",raw[j]);puts("");
    }
    return 0;
}
