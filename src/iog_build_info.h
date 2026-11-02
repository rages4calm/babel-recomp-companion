/* Public build identity, retained in the binary for the packaging gate. */
#pragma once
#if defined(SNESRECOMP_INTERPRETER_ONLY) && SNESRECOMP_INTERPRETER_ONLY
#define IOG_EXECUTION_ID "IOG_EXECUTION=interpreter-only;rom-derived-code=none"
#else
#define IOG_EXECUTION_ID "IOG_EXECUTION=mixed-aot;rom-derived-code=private"
#endif
