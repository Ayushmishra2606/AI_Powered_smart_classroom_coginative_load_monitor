from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import asyncio
from ai.rtc_manager import RTCManager

rtc_bp = Blueprint('rtc', __name__, url_prefix='/rtc')

@rtc_bp.route('/offer', methods=['POST'])
@login_required
def offer():
    """
    Endpoint for WebRTC signaling.
    Receives an SDP offer and returns an SDP answer.
    """
    params = request.json
    offer_sdp = params.get("sdp")
    offer_type = params.get("type")
    session_id = params.get("session_id")
    is_teacher = params.get("is_teacher", False)

    if not all([offer_sdp, offer_type, session_id]):
        return jsonify({"error": "Missing parameters"}), 400

    # Run the async RTC handler in a synchronous Flask route
    try:
        # Create a new event loop for this request or use the existing one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        answer = loop.run_until_complete(
            RTCManager.handle_offer(offer_sdp, offer_type, session_id, is_teacher)
        )
        loop.close()
        
        return jsonify(answer)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
