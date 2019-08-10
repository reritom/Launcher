class ResourceManager:
    """
    This class handles the scheduling of resources
    """
    def __init__(self, resources: list):
        self.resources = resources if resources else []

    def add_resource(self, resource):
        self.resources.append(resource)
