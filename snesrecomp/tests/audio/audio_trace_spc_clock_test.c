/* Event-time SPC cycle identity survives delayed export and host-frame changes. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "audio_trace.h"

int snes_frame_counter;
static uint64_t executed_clock;
static unsigned probe_calls;
void RtlApuLock(void) {}
void RtlApuUnlock(void) {}
static uint64_t clock_probe(void) { ++probe_calls; return executed_clock; }
int main(void) {
  AudioTracePortEvent events[4];
  audio_trace_set_spc_clock_probe(clock_probe);
  snes_frame_counter = 7;
  executed_clock = 100;
  audio_trace_on_spc_port_read(0, 0x11);
  executed_clock = 200;
  audio_trace_on_spc_port_write(1, 0x33);
  executed_clock = 300;
  audio_trace_on_cpu_port_write(2, 0x44);
  assert(probe_calls == 2); /* CPU observation time is not an SPC event clock. */
  audio_trace_set_spc_clock_probe(NULL);
  audio_trace_on_spc_port_read(3, 0x55);
  executed_clock = 999;
  snes_frame_counter = 999;
  uint64_t oldest, total;
  assert(audio_trace_copy_port_events(0, 4, events, &oldest, &total) == 4);
  assert(oldest == 0 && total == 4 && probe_calls == 2);
  assert(events[0].apu_cycle == 100 && events[1].apu_cycle == 200);
  assert(events[2].apu_cycle == 0 && events[3].apu_cycle == UINT64_MAX);
  for (unsigned i = 0; i < 4; ++i) assert(events[i].frame == 7);
  puts("SPC event clocks captured before export; CPU sentinel and unavailable probe pass");
  return 0;
}
