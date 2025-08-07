/**
 * @file visualizer_tool.c
 * @version 0.1
 */
// #include <omp.h>
// #include <omp-tools.h>
#include <stdio.h>
#include <time.h>
#include "runtime_visualizer_utils.h"


/**
 * @brief Callback for parallel region begin
 * Called when a thread enters a parallel region
 * @param encountering_task_data Data of the encountering task
 * @param encountering_task_frame Frame of the encountering task
 * @param parallel_data Data of the parallel region
 * @param requested_parallelism Number of threads requested
 * @param flags Flags for the parallel region
 * @param codeptr_ra Return address of the parallel construct
 */
void on_ompt_callback_parallel_begin(
  ompt_data_t *encountering_task_data,
  const ompt_frame_t *encountering_task_frame,
  ompt_data_t *parallel_data,
  unsigned int requested_parallelism,
  int flags,
  const void *codeptr_ra) {
  
  double timestamp = get_timestamp();
  int thread_id = omp_get_thread_num();
  
  printf("[OMPT] Thread %d PARALLEL BEGIN at %.3f ms (requested threads: %u)\n", 
          thread_id, timestamp / 1000.0, requested_parallelism);
}

/**
 * @brief Callback for parallel region end
 * Called when a thread exits a parallel region
 * @param parallel_data Data of the parallel region
 * @param encountering_task_data Data of the encountering task
 * @param flags Flags for the parallel region
 * @param codeptr_ra Return address of the parallel construct
 */
void on_ompt_callback_parallel_end(
  ompt_data_t *parallel_data,
  ompt_data_t *encountering_task_data,
  int flags,
  const void *codeptr_ra) {
  
  double timestamp = get_timestamp();
  int thread_id = omp_get_thread_num();
  
  printf("[OMPT] Thread %d PARALLEL END at %.3f ms\n", 
          thread_id, timestamp / 1000.0);
}

/**
 * @brief Callback for work events (begin and end)
 * Called when a thread starts or finishes executing work (like loop iterations)
 * @param work_type Type of work (loop, sections, etc.)
 * @param endpoint Whether this is begin or end of work
 * @param parallel_data Parallel region data
 * @param task_data Task data
 * @param count Number of work items
 * @param codeptr_ra Return address
 */
void on_ompt_callback_work(
  ompt_work_t work_type,
  ompt_scope_endpoint_t endpoint,
  ompt_data_t *parallel_data,
  ompt_data_t *task_data,
  uint64_t count,
  const void *codeptr_ra) {
  
  double timestamp = get_timestamp();
  int thread_id = omp_get_thread_num();
  
  const char* work_type_str = 
      work_type == ompt_work_loop ? "loop" :
      work_type == ompt_work_sections ? "sections" :
      work_type == ompt_work_single_executor ? "single" :
      work_type == ompt_work_single_other ? "single_other" :
      work_type == ompt_work_workshare ? "workshare" :
      work_type == ompt_work_distribute ? "distribute" :
      work_type == ompt_work_taskloop ? "taskloop" : "unknown";
  
  const char* event_type = (endpoint == ompt_scope_begin) ? "START" : "END";
  
  printf("[OMPT] Thread %d WORK %s at %.3f ms (type: %s, count: %lu)\n", 
          thread_id, event_type, timestamp / 1000.0, work_type_str, count);
}

/**
 * @brief Callback for implicit task events (begin and end)
 * Called when a thread starts or finishes executing an implicit task
 * @param endpoint Whether this is begin or end of the implicit task
 * @param parallel_data Parallel region data
 * @param task_data Task data
 * @param team_size Number of threads in the team
 * @param thread_num Thread number within the team
 * @param flags Task flags
 */
void on_ompt_callback_implicit_task(
  ompt_scope_endpoint_t endpoint,
  ompt_data_t *parallel_data,
  ompt_data_t *task_data,
  unsigned int team_size,
  unsigned int thread_num,
  int flags) {
  
  double timestamp = get_timestamp();
  int thread_id = omp_get_thread_num();
  
  const char* event_type = (endpoint == ompt_scope_begin) ? "TASK START" : "TASK FINISH";
  
  printf("[OMPT] Thread %d %s at %.3f ms (team size: %u)\n", 
          thread_id, event_type, timestamp / 1000.0, team_size);
}

/**
 * @brief Callback for synchronization events (barriers, etc.)
 * Called when threads encounter synchronization points
 * @param kind Type of synchronization (barrier, critical, etc.)
 * @param endpoint Whether this is begin or end of sync
 * @param parallel_data Parallel region data
 * @param task_data Task data
 * @param codeptr_ra Return address
 */
void on_ompt_callback_sync_region(
  ompt_sync_region_t kind,
  ompt_scope_endpoint_t endpoint,
  ompt_data_t *parallel_data,
  ompt_data_t *task_data,
  const void *codeptr_ra) {
  
  double timestamp = get_timestamp();
  int thread_id = omp_get_thread_num();
  
  const char* sync_type_str = 
      kind == ompt_sync_region_barrier ? "barrier" :
      kind == ompt_sync_region_barrier_implicit ? "implicit_barrier" :
      kind == ompt_sync_region_barrier_explicit ? "explicit_barrier" :
      kind == ompt_sync_region_barrier_implementation ? "implementation_barrier" :
      kind == ompt_sync_region_taskwait ? "taskwait" :
      kind == ompt_sync_region_taskgroup ? "taskgroup" :
      kind == ompt_sync_region_reduction ? "reduction" : "unknown";
  
  const char* event_type = (endpoint == ompt_scope_begin) ? "ENTER" : "EXIT";
  
  printf("[OMPT] Thread %d %s %s at %.3f ms\n", 
          thread_id, event_type, sync_type_str, timestamp / 1000.0);
}

/**
* @brief OMPT Tool Initializer.
* This function is called by the OpenMP runtime to initialize the OMPT tool.
* @param lookup Function lookup function provided by the OpenMP runtime.
* @param initial_device_num Initial device number (if applicable).
* @param tool_data Pointer to tool data structure.
* @return int Non-zero to keep the OMPT tool active, zero to disable it.
 */
int initializer(
  ompt_function_lookup_t lookup,
  int initial_device_num,
  ompt_data_t *tool_data) {
  
  printf("OMPT Tool Initialized\n");
  
  // Register callback for thread begin events
  ompt_set_callback_t ompt_set_callback = 
      (ompt_set_callback_t) lookup("ompt_set_callback");
  
  if (ompt_set_callback) {
    // Register parallel region callbacks
    ompt_set_callback(ompt_callback_parallel_begin, 
                     (ompt_callback_t) on_ompt_callback_parallel_begin);
    
    ompt_set_callback(ompt_callback_parallel_end, 
                     (ompt_callback_t) on_ompt_callback_parallel_end);
    
    // Register work callbacks (for tracking actual task execution)
    ompt_set_callback(ompt_callback_work, 
                     (ompt_callback_t) on_ompt_callback_work);
    
    // Register implicit task callbacks
    ompt_set_callback(ompt_callback_implicit_task, 
                     (ompt_callback_t) on_ompt_callback_implicit_task);
    
    // Register synchronization callbacks
    ompt_set_callback(ompt_callback_sync_region, 
                     (ompt_callback_t) on_ompt_callback_sync_region);
    
    printf("OMPT callbacks registered successfully\n");
  } else {
    printf("Warning: Could not register OMPT callbacks\n");
  }

  // Return non-zero to keep the OMPT tool active.
  // Return zero to disable the tool for this execution.
  return 1;
}


/**
 * @brief OMPT Tool Finalizer
 * Called by the OpenMP runtime to finalize the tool.
 * This function can be used to clean up resources allocated by the tool.
 * @param tool_data Pointer to tool data structure
 */
void finalizer(ompt_data_t *tool_data) {
  // This function is called when the OpenMP runtime is done with the tool.
  // Cleanup resources, if any.
  printf("OMPT Tool Finalized\n");
}

/**
 * @brief ompt_start_tool
 * This function is the entry point for the OMPT tool.
 * It is called by the OpenMP runtime to start the tool.
 * It returns a pointer to an ompt_start_tool_result_t structure that contains
 * the initializer and finalizer functions for the tool.
 * @param omp_version 
 * @param runtime_version 
 * @return ompt_start_tool_result_t* 
 */
ompt_start_tool_result_t* ompt_start_tool(
  unsigned int omp_version,
  const char *runtime_version) {
  
  static ompt_start_tool_result_t result;
  result.initialize = initializer;
  result.finalize = finalizer;
  result.tool_data = (ompt_data_t){0}; // Initialize tool_data to zero
  
  return &result;
}