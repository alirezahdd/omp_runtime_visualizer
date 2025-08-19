#ifndef OMPT_ANNOTATION_H
#define OMPT_ANNOTATION_H

#include <stdio.h>
#include <time.h>
#include <stdbool.h>
// #include <sys/time.h>
// #include <omp.h>



bool ompt_loaded = false;
static bool first_call = true;

void check_ompt_loaded() {
  // This function checks if the OMPT tool is loaded
  // It can be used to conditionally execute OMPT-related code
  const char* ompt_tool_libraries = getenv("OMP_TOOL_LIBRARIES");
  if (ompt_tool_libraries != NULL) {
    ompt_loaded = true;
  } else {
    ompt_loaded = false;
  }
}

double get_timestamp() {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec * 1000000.0 + ts.tv_nsec / 1000.0;  // microseconds
}

void ompt_annotate(const char* annotation) {
  // This function can be used to annotate specific points in the code
  // For example, it could log the annotation to a file or console

  if (first_call) {
    check_ompt_loaded();
    first_call = false;
  }

  if (!ompt_loaded) {
    return;  // Silent no-op when OMPT tool is not enabled
  }

  double timestamp = get_timestamp();
  int thread_id = omp_get_thread_num();
  printf("[OMPT_annotation] Thread %d Annotation at %.3f ms: %s\n", 
         thread_id, timestamp / 1000.0, annotation);
}

inline void ompt_mark_roi_start() {
  ompt_annotate("ROI_START");
}

inline void ompt_mark_roi_end() {
  ompt_annotate("ROI_END");
} 

#endif  // OMPT_ANNOTATION_H
