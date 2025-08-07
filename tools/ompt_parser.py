#!/usr/bin/env python3
import sys
import re
from collections import defaultdict, namedtuple

# Event structure
Event = namedtuple("Event", ["timestamp", "thread_id", "event_type", "details"])
Annotation = namedtuple("Annotation", ["timestamp", "thread_id", "label"])


class OMPTParser:
    def __init__(self, filename):
        self.filename = filename
        self.events = []
        self.annotations = []
        self.threads = set()

    def parse_file(self):
        """Parse the OMPT output file and extract events and annotations."""
        print(f"Parsing OMPT output file: {self.filename}")

        with open(self.filename, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Check for annotations first
                if line.startswith("[OMPT_annotation]"):
                    annotation = self._parse_annotation(line)
                    if annotation:
                        self.annotations.append(annotation)
                        self.threads.add(annotation.thread_id)
                    continue

                # Check for regular OMPT events
                if not line.startswith("[OMPT]"):
                    continue

                event = self._parse_line(line)
                if event:
                    self.events.append(event)
                    self.threads.add(event.thread_id)

        self.threads = sorted(list(self.threads))
        print(
            f"Parsed {len(self.events)} events and {len(self.annotations)} annotations for {len(self.threads)} threads"
        )

    def _parse_line(self, line):
        """Parse a single OMPT output line."""
        # Pattern: [OMPT] Thread X EVENT_TYPE at Y.Z ms ...
        pattern = r"\[OMPT\] Thread (\d+) (.+?) at ([\d.]+) ms(?:\s+\((.+?)\))?"
        match = re.match(pattern, line)

        if not match:
            return None

        thread_id = int(match.group(1))
        event_type = match.group(2).strip()
        timestamp = float(match.group(3))
        details = match.group(4) if match.group(4) else ""

        return Event(timestamp, thread_id, event_type, details)

    def _parse_annotation(self, line):
        """Parse a line for OMPT annotations in format [OMPT_annotation] Thread X Annotation at Y.Z ms: LABEL"""
        # Pattern: [OMPT_annotation] Thread X Annotation at Y.Z ms: LABEL
        pattern = r"\[OMPT_annotation\] Thread (\d+) Annotation at ([\d.]+) ms: (.+)"
        match = re.match(pattern, line)

        if not match:
            return None

        thread_id = int(match.group(1))
        timestamp = float(match.group(2))
        label = match.group(3).strip()

        return Annotation(timestamp, thread_id, label)

    def analyze_timeline(self):
        """Analyze events and print timeline information."""
        print("\n" + "=" * 60)
        print("OMPT TIMELINE ANALYSIS")
        print("=" * 60)

        # Sort events by timestamp
        sorted_events = sorted(self.events, key=lambda x: x.timestamp)
        sorted_annotations = sorted(self.annotations, key=lambda x: x.timestamp)

        # Combine events and annotations for chronological display
        all_items = []
        for event in sorted_events:
            all_items.append(("event", event))
        for annotation in sorted_annotations:
            all_items.append(("annotation", annotation))

        # Sort combined items by timestamp
        all_items.sort(key=lambda x: x[1].timestamp)

        print(
            f"\nTimeline of Events and Annotations ({len(sorted_events)} events, {len(sorted_annotations)} annotations):"
        )
        print("-" * 80)

        # Print items in chronological order
        base_time = all_items[0][1].timestamp if all_items else 0
        for i, (item_type, item) in enumerate(all_items):
            relative_time = item.timestamp - base_time
            if item_type == "event":
                print(
                    f"{i+1:3d}. {relative_time:8.2f}ms | Thread {item.thread_id} | {item.event_type}"
                )
                if item.details:
                    print(f"     {' '*10} | Details: {item.details}")
            else:  # annotation
                print(
                    f"{i+1:3d}. {relative_time:8.2f}ms | Thread {item.thread_id} | ANNOTATION: {item.label}"
                )

        # Add annotations section to output
        if self.annotations:
            print(f"\n" + "=" * 60)
            print("ANNOTATIONS SUMMARY")
            print("=" * 60)

            for annotation in sorted_annotations:
                relative_time = annotation.timestamp - base_time
                print(
                    f"  {relative_time:8.2f}ms | Thread {annotation.thread_id} | {annotation.label}"
                )

        # Analyze thread activities
        print(f"\n" + "=" * 60)
        print("THREAD ACTIVITY SUMMARY")
        print("=" * 60)

        thread_events = defaultdict(list)
        base_time = sorted_events[0].timestamp if sorted_events else 0
        for event in sorted_events:
            thread_events[event.thread_id].append(event)

        for thread_id in self.threads:
            events = thread_events[thread_id]
            print(f"\nThread {thread_id} ({len(events)} events):")

            # Find key timings
            task_starts = [e for e in events if e.event_type == "TASK START"]
            work_starts = [e for e in events if e.event_type == "WORK START"]
            work_ends = [e for e in events if e.event_type == "WORK END"]
            barrier_enters = [
                e
                for e in events
                if "ENTER" in e.event_type and "barrier" in e.event_type
            ]
            barrier_exits = [
                e
                for e in events
                if "EXIT" in e.event_type and "barrier" in e.event_type
            ]
            task_finishes = [e for e in events if e.event_type == "TASK FINISH"]

            if task_starts:
                print(
                    f"  First task start: {task_starts[0].timestamp - base_time:.2f}ms"
                )
            if work_starts and work_ends:
                total_work_time = sum(
                    work_ends[i].timestamp - work_starts[i].timestamp
                    for i in range(min(len(work_starts), len(work_ends)))
                )
                print(f"  Total work time: {total_work_time:.2f}ms")
            if barrier_enters and barrier_exits:
                total_barrier_time = sum(
                    barrier_exits[i].timestamp - barrier_enters[i].timestamp
                    for i in range(min(len(barrier_enters), len(barrier_exits)))
                )
                print(f"  Total barrier time: {total_barrier_time:.2f}ms")
            if task_finishes:
                print(
                    f"  Last task finish: {task_finishes[-1].timestamp - base_time:.2f}ms"
                )

        # Parallel region analysis
        print(f"\n" + "=" * 60)
        print("PARALLEL REGION ANALYSIS")
        print("=" * 60)

        parallel_begins = [e for e in sorted_events if e.event_type == "PARALLEL BEGIN"]
        parallel_ends = [e for e in sorted_events if e.event_type == "PARALLEL END"]

        print(f"Number of parallel regions: {len(parallel_begins)}")

        for i in range(min(len(parallel_begins), len(parallel_ends))):
            begin_time = parallel_begins[i].timestamp - base_time
            end_time = parallel_ends[i].timestamp - base_time
            duration = end_time - begin_time
            print(
                f"  Region {i+1}: {begin_time:.2f}ms -> {end_time:.2f}ms (duration: {duration:.2f}ms)"
            )


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 ompt_parser.py <ompt_output_file>")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        parser = OMPTParser(filename)
        parser.parse_file()
        parser.analyze_timeline()

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
