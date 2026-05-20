class DataResourceError(Exception):
    """数据资源层基础异常。"""


class UnknownResourceError(DataResourceError):
    def __init__(self, resource_id: str):
        super().__init__(f"未知 resource id: {resource_id!r}")
        self.resource_id = resource_id


class InvalidParameterError(DataResourceError):
    def __init__(self, message: str, *, param: str | None = None):
        super().__init__(message)
        self.param = param


class ResourceLoadError(DataResourceError):
    pass
