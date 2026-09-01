#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
mkdir -p .design-sync/component-docs

write() {
  printf -- '---\ncategory: %s\n---\n' "$2" > ".design-sync/component-docs/$1.md"
}

write GhostBtn "Buttons"
write LumenBtn "Buttons"
write IconBtn "Buttons"
write ActBtn "Buttons"
write EyeBtn "Buttons"
write Toggle "Buttons"

write ApInput "Inputs"
write ApSelect "Inputs"
write SelectControl "Inputs"

write Dot "Status & Progress"
write HealthPill "Status & Progress"
write StatePill "Status & Progress"
write Bar "Status & Progress"
write MetricRing "Status & Progress"
write Shimmer "Status & Progress"
write ShimmerCard "Status & Progress"
write StageProgress "Status & Progress"

write Chip "Data Display"
write StatBlock "Data Display"
write Counter "Data Display"
write ObjRow "Data Display"
write Meter "Data Display"
write OutputBody "Data Display"
write StageCard "Data Display"
write Muted "Data Display"

write Eyebrow "Layout & Chrome"
write ControlHeader "Layout & Chrome"
write Photo "Layout & Chrome"
write Kbd "Layout & Chrome"

write MagIcon "Icons"
write IconSearch "Icons"
write IconWorkspaces "Icons"
write IconPipelines "Icons"
write IconJobs "Icons"

write PipelineSection "Pipeline Outputs"

write Logo "Brand"

ls .design-sync/component-docs/ | wc -l
