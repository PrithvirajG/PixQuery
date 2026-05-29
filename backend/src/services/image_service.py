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
        # Allow access if: no user filter, asset is unowned, or asset belongs to user
        owner = asset.get("owner_id")
        if user_id and owner is not None and owner != user_id:
            return None
        return serialize_document(asset)
