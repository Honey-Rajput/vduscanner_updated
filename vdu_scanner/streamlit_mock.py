
import sys
class session_state_class(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        return None
    def __setattr__(self, name, value):
        self[name] = value

session_state = session_state_class()

def set_page_config(*args, **kwargs): pass
def title(msg): pass
def markdown(*args, **kwargs): pass
def text(msg): pass
def subheader(msg): pass
def caption(msg): pass
def columns(n): return [st_mock]*n
def tabs(l): return [st_mock]*len(l)
def empty(): return st_mock
def progress(v): return st_mock
def error(msg): print("ST_ERROR:", msg)
def warning(msg): print("ST_WARNING:", msg)
def info(msg): print("ST_INFO:", msg)
def success(msg): print("ST_SUCCESS:", msg)
def dataframe(*args, **kwargs): pass
def plotly_chart(*args, **kwargs): pass
def toast(*args, **kwargs): pass
def stop(): print("ST_STOP"); sys.exit(0)

class sidebar:
    @staticmethod
    def header(msg): pass
    @staticmethod
    def markdown(*args, **kwargs): pass
    @staticmethod
    def title(msg): pass
    @staticmethod
    def selectbox(label, options, *args, **kwargs):
        if "Timeframe" in label: return "Daily (1d)"
        return options[0]
    @staticmethod
    def slider(label, *args, **kwargs):
        if "Dry Zone" in label: return (0, 100)
        return kwargs.get("value", 0)
    @staticmethod
    def number_input(label, *args, **kwargs):
        return kwargs.get("value", 0)
    @staticmethod
    def checkbox(label, *args, **kwargs):
        return kwargs.get("value", False)
    @staticmethod
    def button(label, *args, **kwargs):
        if "Run Scanner" in label:
            return True
        return False
    @staticmethod
    def expander(*args, **kwargs): return st_mock
    @staticmethod
    def error(msg): print("SIDEBAR_ERROR:", msg)
    @staticmethod
    def warning(msg): print("SIDEBAR_WARNING:", msg)

# Self-reference for chaining
st_mock = sys.modules[__name__]
st_mock.sidebar = sidebar
st_mock.session_state = session_state
st_mock.set_page_config = set_page_config
st_mock.title = title
st_mock.markdown = markdown
st_mock.text = text
st_mock.subheader = subheader
st_mock.caption = caption
st_mock.columns = columns
st_mock.tabs = tabs
st_mock.empty = empty
st_mock.progress = progress
st_mock.error = error
st_mock.warning = warning
st_mock.info = info
st_mock.success = success
st_mock.dataframe = dataframe
st_mock.plotly_chart = plotly_chart
st_mock.toast = toast
st_mock.stop = stop

def __getattr__(name):
    def noop(*args, **kwargs): pass
    return noop
