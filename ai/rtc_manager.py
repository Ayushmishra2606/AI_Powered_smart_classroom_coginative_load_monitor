import asyncio
import json
import logging
import uuid
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender

# --- Global RTC State ---
# relay: Takes one input track and can fan it out to many outputs
relay = MediaRelay()
# tracks: Map of session_id -> current teacher audio track
teacher_tracks = {}
# pcs: Set of active peer connections for cleanup
pcs = set()

logger = logging.getLogger("RTC")

class RTCManager:
    @staticmethod
    async def handle_offer(sdp, type, session_id, is_teacher):
        """
        Handles a WebRTC offer from a browser.
        If teacher: receives audio and stores in teacher_tracks.
        If student: relays teacher_tracks[session_id] to the student.
        """
        pc = RTCPeerConnection()
        pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"PC Connection State: {pc.connectionState}")
            if pc.connectionState in ["failed", "closed"]:
                await pc.close()
                pcs.discard(pc)
                if is_teacher and session_id in teacher_tracks:
                    del teacher_tracks[session_id]

        if is_teacher:
            # Teacher is sending audio to the server
            @pc.on("track")
            def on_track(track):
                if track.kind == "audio":
                    logger.info(f"Teacher track received for session {session_id}")
                    teacher_tracks[session_id] = relay.subscribe(track)

                @track.on("ended")
                async def on_ended():
                    logger.info(f"Teacher track ended for session {session_id}")
                    if session_id in teacher_tracks:
                        del teacher_tracks[session_id]
        else:
            # Student wants to receive audio from the server
            track = teacher_tracks.get(session_id)
            if track:
                pc.addTrack(track)
                logger.info(f"Relaying teacher track to student in session {session_id}")
            else:
                logger.warning(f"No active teacher track for session {session_id} to relay to student")

        # Handle negotiation
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

    @staticmethod
    async def cleanup():
        coros = [pc.close() for pc in pcs]
        await asyncio.gather(*coros)
        pcs.clear()
