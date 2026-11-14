#ifndef IOG_MODE7_PERSPECTIVE_H
#define IOG_MODE7_PERSPECTIVE_H
#include <stdbool.h>
#include <stdint.h>

typedef struct IogMode7PerspectiveParameters {
    uint16_t initial_divisor,increment;
    int16_t cosine,sine;
} IogMode7PerspectiveParameters;
typedef enum IogMode7PerspectiveStatus {
    kIogMode7PerspectiveUnknown,
    kIogMode7PerspectiveMatrix,
    kIogMode7PerspectiveSky
} IogMode7PerspectiveStatus;

static inline int16_t IogMode7PerspectiveSigned(unsigned value)
{
    value&=65535u;
    return (int16_t)(value>=32768u?(int)value-65536:(int)value);
}

/* Host-only reproduction of the stock perspective thinker's forward integer
 * recurrence. Row0 is the first generated HDMA word. The current frame driver
 * captures it at rasterline0: visibleline1 uses word1, and line224 retains
 * word223 after the terminator. Callers must bind/validate that phase too.
 * Call Matches on all224 captured rows BEFORE enabling any extension. Table
 * values are supplied by a profile-qualified reader, never embedded here.
 * Negative rows extend the deterministically initialized, normalized producer,
 * not an alleged historical inverse of arbitrary raster state. Its packed
 * depth is (normalized_divisor<<8)+row*normalized_increment. A positive prefix
 * grows monotonically back to row0 below65536, so no carry/renormalization can
 * discard bits: it rejoins the initialized divisor and zero fraction exactly.
 * Depth below256 means integer divisor0: the host deliberately uses Sky there
 * rather than the hardware divide-by-zero ground artifact. Native rows retain
 * exact hardware divide-by-zero results for calibration.
 */
static inline IogMode7PerspectiveStatus IogMode7PerspectiveSample(
    const IogMode7PerspectiveParameters *p,int row,int16_t matrix[4])
{
    if(!p || !matrix || row < -56 || row > 279)return kIogMode7PerspectiveUnknown;
    for(unsigned i=0;i<4;i++)matrix[i]=0;
    unsigned divisor=p->initial_divisor,increment=p->increment,fraction=0;
    unsigned cosine=p->cosine<0?(unsigned)(-(int)p->cosine):(unsigned)p->cosine;
    unsigned sine=p->sine<0?(unsigned)(-(int)p->sine):(unsigned)p->sine;
    while(divisor&0xff00u){divisor>>=1;increment>>=1;cosine>>=1;sine>>=1;}
    if(row<0) {
        int64_t depth=(int64_t)divisor*256+(int64_t)increment*row;
        if(depth<256)return kIogMode7PerspectiveSky;
        divisor=(unsigned)depth>>8;fraction=(unsigned)depth&255u;
        row=0;
    }
    for(int k=0;k<=row;k++) {
        unsigned c=divisor?cosine/divisor:65535u;
        unsigned s=divisor?sine/divisor:65535u;
        if(k==row) {
            matrix[0]=matrix[3]=IogMode7PerspectiveSigned(p->cosine<0?0u-c:c);
            matrix[1]=IogMode7PerspectiveSigned(p->sine<0?0u-s:s);
            matrix[2]=IogMode7PerspectiveSigned(p->sine<0?s:0u-s);
            return kIogMode7PerspectiveMatrix;
        }
        unsigned sum=((divisor&255u)<<8|fraction)+increment;
        fraction=sum&255u;divisor=(divisor&0xff00u)|((sum>>8)&255u);
        if(sum>65535u) {
            divisor=(divisor+256u)>>1;
            cosine>>=1;sine>>=1;increment>>=1;
            /* Fraction is intentionally NOT shifted by the original code. */
        }
    }
    return kIogMode7PerspectiveUnknown;
}

static inline bool IogMode7PerspectiveMatches(const IogMode7PerspectiveParameters *p,
    const int16_t captured[224][4])
{
    if(!p || !captured)return false;
    for(int row=0;row<224;row++) {
        int16_t matrix[4];
        if(IogMode7PerspectiveSample(p,row,matrix)!=kIogMode7PerspectiveMatrix)return false;
        for(unsigned i=0;i<4;i++)if(matrix[i]!=captured[row][i])return false;
    }
    return true;
}
#endif
