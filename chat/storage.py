from cloudinary_storage.storage import MediaCloudinaryStorage

class MixedMediaCloudinaryStorage(MediaCloudinaryStorage):
    """
    Storage custom để tự động nhận diện resource_type (image/video/raw)
    khi upload lên Cloudinary.
    """
    def _get_resource_type(self, name):
        return 'auto'