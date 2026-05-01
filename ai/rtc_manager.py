import asyncio
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay

logger = logging.getLogger(__name__)

class RTCManager:
    def __init__(self):
        self.classrooms = {}  # session_id -> {'relay': MediaRelay, 'teacher_track': None, 'pcs': set()}
        self.loop = asyncio.new_event_loop()
        import threading
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def get_classroom(self, session_id):
        if session_id not in self.classrooms:
            self.classrooms[session_id] = {
                'relay': MediaRelay(),
                'teacher_track': None,
                'pcs': set()
            }
        return self.classrooms[session_id]

    async def handle_offer(self, session_id, sdp, type, is_teacher):
        pc = RTCPeerConnection()
        classroom = self.get_classroom(session_id)
        classroom['pcs'].add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState in ["failed", "closed"]:
                classroom['pcs'].discard(pc)
                await pc.close()

        if is_teacher:
            @pc.on("track")
            def on_track(track):
                if track.kind == "audio":
                    logger.info(f"Teacher started audio in session {session_id}")
                    classroom['teacher_track'] = classroom['relay'].subscribe(track)

        else:
            # Student: Subscribe to teacher if available
            if classroom['teacher_track']:
                pc.addTrack(classroom['teacher_track'])
            else:
                # If teacher hasn't started yet, we might need a way to add track later
                # For now, students should reconnect when teacher goes live
                pass

        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

# Global instance
rtc_manager = RTCManager()
