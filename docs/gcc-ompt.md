# ompt and gcc compatibility nightmare
<p align="center">
  <img src="../assets/gcc-ompt.png" alt="statistics" width="80%" />
</p>

GCC’s OpenMP implementation, `libgomp`, [does **not** support OMPT](https://www.openmp.org/resources/openmp-compilers-tools/#compilers) (OpenMP Tools Interface). So if you want to use ompt tools you have to use the llvm’s clang and runtime. However, if you have to use the gcc, the following trick might help you. Good news is that, It is still possible to compile your programs using gcc while utilizing ompt by linking against the LLVM implementation of OpenMP (`libomp`) and using its OpenMP-related header files.

While it is generally **safe to link** LLVM’s OpenMP libraries (e.g., `libomp.so`) in GCC using the `-L`  and `-lomp` flags—*as long as these libraries are compatible with GCC’s linker and runtime*—it is **not** safe to include LLVM’s Clang internal headers. These headers may contain Clang-specific macros like `__has_feature`, which GCC does not understand. This often leads to preprocessing or compilation errors. In other words, in the following command, the highlighted part is unsafe.
|            | Command                                                      |
|:----------:|--------------------------------------------------------------|
| **safe**   | `gcc -L /path/to/llvm/lib your_program.c`                    |
| **unsafe** | `gcc -L /path/to/llvm/lib -I /path/to/llvm/include your_program.c` |

The **good news** is that `omp.h` and `omp-tools.h`—the headers required for OpenMP Tools—**do not contain Clang-specific macros** and are compatible with GCC.
* In **LLVM ≤ 10**, these headers were often installed in a **dedicated directory**, e.g., `/usr/lib/llvm-10/include/openmp/`, which contains only OpenMP headers. It was therefore safe to add this path using -I.
* In **LLVM > 10**, however, these headers were moved into a **flat include path** along with other Clang internal headers. In this case, using -I to add the full directory becomes unsafe, since GCC might prioritize and pick up incompatible headers, leading to errors.
So far, If you have llvm-10 or older versions you are fine and the following command is considered safe:
`gcc -fopenmp -L /path/to/llvm/lib -lomp -I /path/to/llvm/include your_program.c`
But, if you have more recent versions of llvm, you should use `-include` flag instead of `-I` to include headers one by one and not the entire directory. For example: 
```
gcc \
-fopenmp -lomp \
-include /usr/lib/llvm-18/lib/clang/18/include/omp.h \
-include /usr/lib/llvm-18/lib/clang/18/include/omp-tools.h \
your_program.c
```
This is **functionally equivalent** to adding the following lines at the top of your_program.c:
```
#include <omp.h>
#include <omp-tools.h>
```
however, the headers are from llvm implementation and not the gcc’s. 
You should also ensure that your_program.c, and any include headers, do not already include `omp.h` nor `omp-tools.h` inside their source code. If they do, GCC may pull in its own OpenMP headers (libgomp), causing **conflicts and redefinitions** when also using LLVM’s headers using `-include` flag in the compile command. To avoid this, manually remove those `#include` lines from your source code.

If everything goes well here, you should get the binary after compiling `your_program.c`.
Assuming you have your ompt tool as a shared library `your_ompt_tool.so`, which is also compiled using the same version of the llvm headers and libs, you can run `your_program` and link it with your tool. For that, you need to tell the runtime to use llvm’s `libomp` instead of gcc’s `libgomp`. To do that you need to prepend the `LD_LIBRARY_PATH` enviroment variable with the path to llvm libs. For example
```
LD_LIBRARY_PATH=/usr/lib/llvm-18/lib:$LD_LIBRARY_PATH
```
Moreover, you need to tell the openmp runtime to load your tool. For that, you need to set the `OMP_TOOL_LIBRARIES` enviroment variable to the path to `your_ompt_tool.so`. 
```
OMP_TOOL_LIBRARIES=/path/to/your_ompt_tool.so
```
 You can either export mentioned enviroment variable or prepend them to your run command. 


