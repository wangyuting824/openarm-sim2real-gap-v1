"""Start the currently loaded Isaac timeline without changing the stage or robot.

Run only through the Isaac-side gap-control daemon.  This is needed before an
RTF probe because a live Kit update loop can exist while PhysX is paused.
"""
import omni.timeline


timeline = omni.timeline.get_timeline_interface()
timeline.play()
print(
    "OPENARM_TIMELINE_PLAY requested playing=%s current_time_s=%.6f"
    % (timeline.is_playing(), float(timeline.get_current_time()))
)
