from src.services.document_serializer import serialize_document, serialize_documents


class ImageService:
    def __init__(self, repository):
        self.repository = repository

    def list_images(self, *, user_id: str | None = None, limit: int = 100, skip: int = 0):
        assets = self.repository.list_active_assets(user_id=user_id, limit=limit, skip=skip)
        return serialize_documents(assets)

    def get_image(self, asset_id: str, *, user_id: str | None = None):
        asset = self.repository.get_asset(asset_id)
        if not asset or not asset.get("active"):
            return None
        # Access is granted when the asset is observed in a workspace the user can reach.
        if user_id is not None and not self.repository.can_access_asset(user_id, asset_id):
            return None
        return serialize_document(asset)

    def get_image_detail(self, asset_id: str, *, user_id: str | None = None):
        """Image plus its caption, detections, and processing provenance.

        Provenance lets the detail view explain where each signal came from:
        which model/version produced it, which pipeline node and run, and when.
        """
        asset = self.get_image(asset_id, user_id=user_id)
        if not asset:
            return None

        outputs = list(self.repository.model_outputs.find({"asset_id": asset_id}))
        caption = next(
            (o["payload"].get("text", "") for o in outputs if o.get("output_type") == "caption"),
            "",
        )
        # Merge every detections output (object + face detectors may each emit one)
        # so the overlay shows all boxes, not just the first detector's.
        detections: list = []
        for o in outputs:
            if o.get("output_type") == "detections":
                detections.extend(o["payload"].get("detections", []) or [])
        return {
            **asset,
            "description": caption,
            "detections": detections,
            "provenance": self._build_provenance(asset_id, outputs),
        }

    def _build_provenance(self, asset_id: str, outputs: list[dict]):
        """Group an asset's outputs by the pipeline that produced them.

        Each output carries a denormalized ``pipeline_id`` (falling back to its
        run's pipeline for older rows); we resolve the pipeline name, attach the
        latest run's status, and expose a compact summary + the payload so the
        detail view can render real content instead of "not exposed".
        """
        runs = list(self.repository.pipeline_runs.find({"asset_id": asset_id}))
        run_by_id = {r["_id"]: r for r in runs}

        groups: dict = {}
        for o in outputs:
            pid = o.get("pipeline_id") or (run_by_id.get(o.get("pipeline_run_id")) or {}).get("pipeline_id")
            groups.setdefault(pid, []).append(o)

        pipelines = []
        for pid, outs in groups.items():
            outs.sort(key=lambda x: (x.get("order") is None, x.get("order") or 0))
            runs_for = [r for r in runs if r.get("pipeline_id") == pid]
            latest = max(runs_for, key=lambda r: r.get("started_at") or "", default=None)
            pipelines.append({
                "pipeline_id": pid,
                "name": self._pipeline_name(pid),
                "pipeline_version": (latest or {}).get("pipeline_version")
                    or (outs[0].get("pipeline_version") if outs else None),
                "status": (latest or {}).get("status"),
                "started_at": _iso((latest or {}).get("started_at")),
                "finished_at": _iso((latest or {}).get("finished_at")),
                "outputs": [self._output_item(o) for o in outs],
            })
        pipelines.sort(key=lambda p: (p["name"] or "").lower())
        return {"pipelines": pipelines}

    def _pipeline_name(self, pipeline_id):
        if not pipeline_id:
            return "Default pipeline"
        definition = self.repository.get_pipeline(pipeline_id)
        return (definition or {}).get("name") or pipeline_id

    @staticmethod
    def _output_item(o: dict):
        payload = o.get("payload") or {}
        return {
            "output_type": o.get("output_type"),
            "model_name": o.get("model_name"),
            "model_version": o.get("model_version"),
            "node_type": o.get("node_type"),
            "order": o.get("order"),
            "created_at": _iso(o.get("created_at")),
            "summary": _summarize(o.get("output_type"), payload),
            "payload": payload,
        }


def _summarize(output_type: str, payload: dict) -> str:
    """A short human-readable line describing an output's payload."""
    if output_type == "caption":
        return payload.get("text", "") or "—"
    if output_type == "ocr":
        text = (payload.get("text") or "").strip().replace("\n", " ")
        return (text[:120] + "…") if len(text) > 120 else (text or "—")
    if output_type == "detections":
        dets = payload.get("detections", []) or []
        labels = _top_labels([d.get("label") for d in dets])
        return f"{len(dets)} detection{'' if len(dets) == 1 else 's'}" + (f": {labels}" if labels else "")
    if output_type == "labels":
        labels = payload.get("labels", []) or []
        return ", ".join(f"{l.get('label')} ({float(l.get('confidence', 0)):.2f})" for l in labels[:3]) or "—"
    if output_type == "metadata":
        meta = payload.get("metadata", {}) or {}
        bits = []
        if meta.get("width") and meta.get("height"):
            bits.append(f"{meta['width']}×{meta['height']}")
        for key in ("camera_make", "camera_model", "datetime_original"):
            if meta.get(key):
                bits.append(str(meta[key]))
        if meta.get("gps_latitude") is not None and meta.get("gps_longitude") is not None:
            bits.append(f"GPS {meta['gps_latitude']:.4f},{meta['gps_longitude']:.4f}")
        return " · ".join(bits) or "dimensions only"
    if output_type == "written_image":
        wi = payload.get("written_image", {}) or {}
        return wi.get("path", "—")
    # generic: list the payload keys
    return ", ".join(payload.keys()) or "—"


def _top_labels(labels: list, limit: int = 3) -> str:
    counts: dict = {}
    for label in labels:
        if label:
            counts[label] = counts.get(label, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return ", ".join(f"{name}×{n}" if n > 1 else name for name, n in ordered)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value
