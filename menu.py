"""AJ Tools startup."""
import nuke
if nuke.GUI:
    import aj_tools
    aj_tools.register()
