#!/usr/bin/env python3
import sys
import re
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import defaultdict

# Color scheme for different states
COLORS = {
    'active': "#14B773",         		# Green - actively working
    'idle_barrier': "#FFC504",   		# Orange - waiting at barrier within parallel region
    'idle_sequential': "#B70000FF", 	# Red - idle between parallel regions
    'background': '#ECEFF1',     		# Light gray - background
}

class TimelineEvent:
    def __init__(self, time, thread_id, event_type, details=""):
        self.time = time
        self.thread_id = thread_id
        self.event_type = event_type
        self.details = details

class TimelineAnnotation:
    def __init__(self, time, thread_id, label):
        self.time = time
        self.thread_id = thread_id
        self.label = label

class TimelinePlotter:
    def __init__(self, parser_output_file):
        self.parser_output_file = parser_output_file
        self.events = []
        self.annotations = []
        self.threads = set()
        self.parallel_regions = []
        self.thread_states = defaultdict(list)
        self.parallel_end_events = []  # Track PARALLEL END events
        
    def parse_output_file(self):
        """Parse the text output from ompt_parser.py"""
        print(f"Reading parser output: {self.parser_output_file}")
        
        with open(self.parser_output_file, 'r') as f:
            content = f.read()
        
        # Extract events from the timeline section
        timeline_section = re.search(r'Timeline of Events.*?(?=^=)', content, re.MULTILINE | re.DOTALL)
        if not timeline_section:
            raise ValueError("Could not find timeline section in parser output")
        
        timeline_text = timeline_section.group(0)
        
        # Parse individual events and annotations
        # Pattern for events: "  1.     0.00ms | Thread 0 | TASK START"
        # Pattern for annotations: "  1.     0.00ms | Thread 0 | ANNOTATION: label"
        event_pattern = r'\s*\d+\.\s*([\d.]+)ms\s*\|\s*Thread\s+(\d+)\s*\|\s*(.+?)(?:\n|$)'
        
        for match in re.finditer(event_pattern, timeline_text):
            time = float(match.group(1))
            thread_id = int(match.group(2))
            event_content = match.group(3).strip()
            
            # Check if this is an annotation
            if event_content.startswith('ANNOTATION:'):
                annotation_label = event_content.replace('ANNOTATION:', '').strip()
                self.annotations.append(TimelineAnnotation(time, thread_id, annotation_label))
            else:
                # Regular event
                self.events.append(TimelineEvent(time, thread_id, event_content))
                
                # Track PARALLEL END events (only from master thread)
                if event_content == 'PARALLEL END' and thread_id == 0:
                    self.parallel_end_events.append(time)
            
            self.threads.add(thread_id)
        
        self.threads = sorted(list(self.threads))
        print(f"Parsed {len(self.events)} events and {len(self.annotations)} annotations for {len(self.threads)} threads")
        print(f"Found {len(self.parallel_end_events)} parallel region endings")
        
    def analyze_thread_states(self):
        """Convert events into thread state timelines with enhanced idle state logic"""
        print("Analyzing thread states ...")
        
        # Initialize thread states
        for thread_id in self.threads:
            self.thread_states[thread_id] = []
        
        # Track current state of each thread
        thread_status = {}
        master_thread = 0
        
        # Sort events by time
        sorted_events = sorted(self.events, key=lambda x: x.time)

				# Initialize thread status. Master starts as active, others as idle_sequential
        for thread_id in self.threads:
            if thread_id == master_thread:
                thread_status[thread_id] = {'state': 'active', 'start_time': 0}
            else:
                thread_status[thread_id] = {'state': 'idle_sequential', 'start_time': 0}
        
        for event in sorted_events:
            thread_id = event.thread_id
            
            # Initialize thread status if not exists. It is unlikely to happen :)
            if thread_id not in thread_status:
                if thread_id == master_thread:
                    thread_status[thread_id] = {'state': 'active', 'start_time': 0}
            
            # Handle different event types
            
            # PARALLEL BEGIN and END are only called from master thread
            if event.event_type == 'PARALLEL BEGIN':
                if thread_id == master_thread:
                    self.parallel_regions.append(event.time)
                
            elif event.event_type == 'PARALLEL END':
                if thread_id == master_thread:
                    # When master thread ends parallel region, all threads should go to idle_barrier
                    for tid in self.threads:
                        if tid in thread_status:
                            # End current state
                            current_state = thread_status[tid]['state']
                            duration = event.time - thread_status[tid]['start_time']
                            if duration > 0.01:  # Only record if > 0.01ms
                                if tid != master_thread:			# Non-master threads
                                    self.thread_states[tid].append({
                                        'start': thread_status[tid]['start_time'],
                                        'end': event.time,
                                        'state': current_state
                                    })
                                else:													# Master thread		
                                    self.thread_states[tid].append({
                                        'start': thread_status[tid]['start_time'],
                                        'end': event.time,
                                        'state': 'active'
                                    })
                            
                            # Start idle_sequential state for all non-master threads
                            if tid != master_thread:
                                thread_status[tid] = {'state': 'idle_sequential', 'start_time': event.time}
                            # Master thread remains active
                            else:
                                thread_status[tid] = {'state': 'active', 'start_time': event.time}
                
            elif event.event_type == 'TASK START':
                # End current state and start task
                current_state = thread_status[thread_id]['state']
                duration = event.time - thread_status[thread_id]['start_time']
                if duration > 0.01:  # Only record if > 0.01ms
                    # If we were in idle_barrier, switch to idle_sequential just before task start
                    # if current_state == 'idle_barrier':
                    #     # Add a very short idle_sequential period
                    #     self.thread_states[thread_id].append({
                    #         'start': thread_status[thread_id]['start_time'],
                    #         # 'end': event.time - 0.01,  # End just before task start
                    #         'end': event.time,  # End at task start
                    #         'state': 'idle_barrier'
                    #     })
                    # else:
                    #     self.thread_states[thread_id].append({
                    #         'start': thread_status[thread_id]['start_time'],
                    #         'end': event.time,
                    #         'state': current_state
                    #     })
                    self.thread_states[thread_id].append({
                            'start': thread_status[thread_id]['start_time'],
                            'end': event.time,
                            'state': current_state
                        })    
                thread_status[thread_id] = {'state': 'active', 'start_time': event.time}
                
            elif event.event_type == 'WORK START':
                # End task_ready state and start active work
                current_state = thread_status[thread_id]['state']
                duration = event.time - thread_status[thread_id]['start_time']
                if duration > 0.01:  # Only record if > 0.01ms
                    # Task setup time is considered idle_sequential
                    # state_type = 'idle_sequential' if current_state == 'task_ready' else current_state
                    self.thread_states[thread_id].append({
                        'start': thread_status[thread_id]['start_time'],
                        'end': event.time,
                        'state': current_state
                    })
                thread_status[thread_id] = {'state': 'active', 'start_time': event.time}
                
            elif event.event_type == 'WORK END':
                # End active work
                current_state = thread_status[thread_id]['state']
                if thread_status[thread_id]['state'] == 'active':
                    self.thread_states[thread_id].append({
                        'start': thread_status[thread_id]['start_time'],
                        'end': event.time,
                        'state': current_state
                    })
                thread_status[thread_id] = {'state': 'idle_barrier', 'start_time': event.time}
                
            elif 'ENTER' in event.event_type and 'barrier' in event.event_type:
                # End current state and start barrier wait (idle_barrier)
                current_state = thread_status[thread_id]['state']
                duration = event.time - thread_status[thread_id]['start_time']
                if duration > 0.1:  # Only record if > 0.1ms
                    if current_state == 'active':
                        state_type = 'active'
                    elif current_state == 'idle_barrier':
                        state_type = 'idle_barrier'  # Post-work waiting is barrier waiting
                    else:
                        state_type = current_state
                        
                    self.thread_states[thread_id].append({
                        'start': thread_status[thread_id]['start_time'],
                        'end': event.time,
                        'state': state_type
                    })
                thread_status[thread_id] = {'state': 'idle_barrier', 'start_time': event.time}
                
            elif 'EXIT' in event.event_type and 'barrier' in event.event_type:
                # For non-master threads, ignore barrier exit if it happens after PARALLEL END
                # because they're exiting a barrier from the previous region
                if thread_id != master_thread:
                    # Check if this exit happens after any PARALLEL END
                    is_cross_region_exit = any(pe_time < event.time for pe_time in self.parallel_end_events)
                    if is_cross_region_exit:
                        # This is a cross-region barrier exit, don't record it as ending idle_barrier
                        continue
                
                # End barrier wait for master thread or valid exits
                if thread_status[thread_id]['state'] == 'idle_barrier':
                    self.thread_states[thread_id].append({
                        'start': thread_status[thread_id]['start_time'],
                        'end': event.time,
                        'state': 'idle_barrier'
                    })
                
                thread_status[thread_id] = {'state': 'active', 'start_time': event.time}
            elif event.event_type == 'TASK FINISH':
                # For non-master threads, ignore task finish if it happens after PARALLEL END
                # because they're finishing a task from the previous region
                if thread_id != master_thread:
                    # Check if this finish happens after any PARALLEL END
                    is_cross_region_finish = any(pe_time < event.time for pe_time in self.parallel_end_events)
                    if is_cross_region_finish:
                        # This is a cross-region task finish, don't process it
                        continue
                
                # End current state
                current_state = thread_status[thread_id]['state']
                duration = event.time - thread_status[thread_id]['start_time']
                if duration > 0.1:  # Only record if > 0.1ms
                    # if current_state == 'active':
                    #     state_type = 'idle_barrier'
                    # elif current_state == 'post_work':
                    #     state_type = 'idle_barrier'
                    # else:
                    #     state_type = current_state
                        
                    self.thread_states[thread_id].append({
                        'start': thread_status[thread_id]['start_time'],
                        'end': event.time,
                        'state': current_state
                    })
                if thread_id != master_thread:
                    thread_status[thread_id] = {'state': 'idle_sequential', 'start_time': event.time}
                else:
                    thread_status[thread_id] = {'state': 'active', 'start_time': event.time}
        
        # Handle final states
        if sorted_events:
            max_time = max(event.time for event in sorted_events)
            for thread_id, status in thread_status.items():
                if status['start_time'] < max_time:
                    duration = max_time - status['start_time']
                    if duration > 0.1:  # Only record if > 0.1ms
                        final_state = 'idle_sequential'
                        if status['state'] in ['idle_barrier', 'post_barrier']:
                            final_state = 'idle_barrier'
                        elif status['state'] in ['active']:
                            final_state = 'active'
                            
                        self.thread_states[thread_id].append({
                            'start': status['start_time'],
                            'end': max_time,
                            'state': final_state
                        })
    
    def create_timeline_plot(self, output_file='thread_timeline.png'):
        """Create and save the timeline visualization"""
        print(f"Creating timeline visualization: {output_file}")
        
        if not self.events:
            print("No events to plot")
            return
            
        # Calculate figure size
        num_threads = len(self.threads)
        fig_width = 14
        fig_height = max(8, num_threads * 0.5 )
        
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        
        # Calculate time range
        min_time = min(event.time for event in self.events)
        max_time = max(event.time for event in self.events)
        time_range = max_time - min_time
        
        # Set up the plot
        ax.set_xlim(min_time - time_range * 0.02, max_time + time_range * 0.02)
        ax.set_ylim(-0.5, num_threads - 0.5)
        
        # Draw thread timelines
        bar_height = 0.7
        for i, thread_id in enumerate(self.threads):
            y_pos = num_threads - 1 - i
            
            # Draw background
            ax.barh(y_pos, max_time - min_time, height=bar_height, 
                   left=min_time, color=COLORS['background'], alpha=0.3)
            
            # Draw thread states
            for state_info in self.thread_states[thread_id]:
                duration = state_info['end'] - state_info['start']
                if duration > 0:
                    color = COLORS.get(state_info['state'], COLORS['background'])
                    ax.barh(y_pos, duration, height=bar_height,
                           left=state_info['start'], color=color, alpha=0.9)
                          #  linewidth=0.1)
                        #    edgecolor='white', linewidth=0.5)
        
        # Add annotation markers as vertical dashed lines
        if self.annotations:
            print(f"Adding {len(self.annotations)} annotation markers")
            for annotation in self.annotations:
                ax.axvline(x=annotation.time, color='#2c3e50', 
                          linestyle='--', alpha=0.8, linewidth=0.5)
                
                # Add annotation label at the top
                ax.text(annotation.time, num_threads - 0.1, annotation.label, 
                       rotation=90, ha='right', va='bottom', fontsize=8,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='#ecf0f1', 
                                alpha=0.9, edgecolor='#2c3e50', linewidth=1))
        
        # Customize the plot
        ax.set_xlabel('Time (ms)', fontsize=12)
        ax.set_ylabel('Thread ID', fontsize=12)
        # ax.set_title('OpenMP Thread Timeline Analysis', 
        #             fontsize=14, fontweight='bold')
        
        # Set thread labels
        ax.set_yticks(range(num_threads))
        ax.set_yticklabels([f'Thread {tid}' for tid in reversed(self.threads)])
        
        # Add legend
        legend_elements = [
            patches.Patch(color=COLORS['active'], label='Active (Working)'),
            patches.Patch(color=COLORS['idle_barrier'], label='Idle - Sync Wait'),
            patches.Patch(color=COLORS['idle_sequential'], label='Idle - Sequential Region'),
        ]
        
        # Add annotation legend entry if annotations exist
        if self.annotations:
            legend_elements.append(
                plt.Line2D([0], [0], color='#2c3e50', 
                          linestyle='--', linewidth=1, label='Annotations')
            )
        
				# Place the legend outside the plot, on the left top corner of the entire figure
        fig.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0.01, 0.99), fontsize=10, frameon=True)
        
        # Grid and formatting
        ax.grid(True, alpha=0.3, axis='x')
        ax.set_axisbelow(True)
        
        # Format x-axis to show time in seconds if > 10000ms
        if max_time > 10000:
            # Convert to seconds for readability
            ax.set_xlabel('Time (s)', fontsize=12)
            current_ticks = ax.get_xticks()
            ax.set_xticklabels([f'{tick/1000:.1f}' for tick in current_ticks])
        
        plt.tight_layout()
        plt.savefig(output_file.replace('.png', '.pdf'), format='pdf', dpi=300, bbox_inches='tight')
        print(f"Timeline saved as: {output_file}")

        # Print statistics
        self._print_statistics()
    
    def _print_statistics(self):
        """Print timeline statistics"""
        print("\n" + "="*60)
        print("TIMELINE STATISTICS")
        print("="*60)
        
        total_times = defaultdict(float)
        
        for thread_id in self.threads:
            thread_total = defaultdict(float)
            
            for state_info in self.thread_states[thread_id]:
                duration = state_info['end'] - state_info['start']
                state = state_info['state']
                thread_total[state] += duration
                total_times[state] += duration
            
            total_time = sum(thread_total.values())
            if total_time > 0:
                print(f"\nThread {thread_id}:")
                print(f"  Active:          {thread_total['active']:8.2f} ms ({thread_total['active']/total_time*100:5.1f}%)")
                print(f"  Idle-Barrier:    {thread_total['idle_barrier']:8.2f} ms ({thread_total['idle_barrier']/total_time*100:5.1f}%)")
                print(f"  Idle-Sequential: {thread_total['idle_sequential']:8.2f} ms ({thread_total['idle_sequential']/total_time*100:5.1f}%)")
                print(f"  Total:           {total_time:8.2f} ms")
        
        # Overall statistics
        overall_total = sum(total_times.values())
        if overall_total > 0:
            print(f"\nOverall (all threads combined):")
            print(f"  Active:          {total_times['active']:8.2f} ms ({total_times['active']/overall_total*100:5.1f}%)")
            print(f"  Idle-Barrier:    {total_times['idle_barrier']:8.2f} ms ({total_times['idle_barrier']/overall_total*100:5.1f}%)")
            print(f"  Idle-Sequential: {total_times['idle_sequential']:8.2f} ms ({total_times['idle_sequential']/overall_total*100:5.1f}%)")
            print(f"  Total:           {total_times['idle_sequential'] + total_times['idle_barrier'] + total_times['active']:8.2f} ms")
        
        # Print annotation information if any exist
        if self.annotations:
            print(f"\nAnnotations found ({len(self.annotations)} total):")
            for annotation in sorted(self.annotations, key=lambda x: x.time):
                print(f"  {annotation.time:8.2f}ms | Thread {annotation.thread_id} | {annotation.label}")

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python3 timeline_plotter.py <parser_output_file>")
        print("Example: python3 timeline_plotter.py parser_output.txt")
        sys.exit(1)
    
    parser_output_file = sys.argv[1]
    output_plot_file = sys.argv[2] if len(sys.argv) > 2 else 'thread_timeline.png'
    try:
        plotter = TimelinePlotter(parser_output_file)
        plotter.parse_output_file()
        plotter.analyze_thread_states()
        plotter.create_timeline_plot(output_file=output_plot_file)
        
    except FileNotFoundError:
        print(f"Error: File '{parser_output_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
