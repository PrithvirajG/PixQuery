---
project: PixQuery
type: knowledge-note
created: 2026-10-01
status: parked
---

# Vision Language Model — GPU Memory Fit (Parked)

Captioning was redesigned and renamed to a general **Vision Language Model** node (`node_type: vision_language_model`, migration `0003_rename_captioning_to_vision_language_model`): instead of only BLIP's fixed unconditioned caption, the node now takes a configurable **prompt** and offers a choice of real instruction-following VLMs — same multi-model `ModelSpec` pattern as every other AI node (Object Detection, Face Detection, Classification, Embedding).

Two prompt-capable models were evaluated for the initial lineup. Both are shipped as selectable options (BLIP stays the fast, always-fits default); neither is a good experience on a small GPU today.

## Measured, on an NVIDIA GeForce GTX 1650 (4GB VRAM), fp16

| | Qwen2-VL-2B-Instruct | Moondream2 |
|---|---|---|
| Load time | 16s | 230s |
| Peak VRAM | 5.03 GB | 5.28 GB |
| Time per prompt | ~115s | ~116s |
| Prompt-following quality | Good (verified against 3 distinct prompts on a real photo) | Good |

Both exceed the card's 4GB ceiling. Windows' WDDM driver doesn't hard-error on this like Linux CUDA would — it silently pages the overflow into shared system RAM over PCIe, so the job still completes, just at a crawl (~2 min per image for this one stage — impractical for a real pipeline run of any size).

Moondream2 was expected to be the lighter option (it's marketed as such) and wasn't — on this card it's no better than Qwen2-VL, and slower to load. That assumption should not be repeated without re-measuring.

One real compatibility bug hit along the way, now known: the `vikhyatk/moondream2` revision pinned to `2024-08-26` crashes under `transformers==4.52.4` (`AttributeError: 'PhiForCausalLM' object has no attribute 'generate'` — `transformers>=4.50` stopped having `PreTrainedModel` auto-inherit `GenerationMixin`, and that revision's bundled modeling code predates the fix). The unpinned/latest revision works. If re-visiting Moondream2, don't pin an old revision.

## Decision (2026-10-01)

Hold on fixing the VRAM fit for now. Ship Qwen2-VL-2B-Instruct and Moondream2 as selectable models as-is (correct, just GPU-hungry/slow on small cards) rather than block the feature on this. Noted here so it isn't re-litigated from scratch later.

## Future work, when revisited

- **4-bit quantization via `bitsandbytes`** for one or both models — plausible path to getting peak VRAM under ~2GB and restoring normal (seconds, not minutes) inference speed on small cards. Not yet tested.
- A genuinely **lighter weight-class model** (sub-1B prompt-following VLM) as a third option, once one with solid prompt-following quality is identified — Moondream2 turned out not to be meaningfully lighter in practice on this hardware, so don't assume a model's marketing size claim without measuring.
- Worth re-measuring on a GPU with more headroom (8GB+) before assuming either model is impractical in general — these numbers are specific to a 4GB card.

Related: [[Stage Model Quality Audit]] (the general "config/model fields were decorative" root cause this node's redesign grew out of) · [[Pipeline Stage Reference]]
