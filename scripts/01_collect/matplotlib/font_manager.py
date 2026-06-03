class FontProperties:
    def __init__(self, *args, **kwargs):
        pass

class FontEntry:
    def __init__(self, *args, **kwargs):
        self.name = kwargs.get('name', 'dummy')
        self.fname = kwargs.get('fname', 'dummy')

def fontManager(*args, **kwargs):
    pass

class _FontManager:
    def __init__(self):
        self.ttflist = []
    def addfont(self, *args, **kwargs):
        pass

fontManager = _FontManager()
