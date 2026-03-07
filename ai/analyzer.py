"""
AI Analyzer — Simulates real-time student attention & cognitive load analysis.
In production, replace simulate_student() with actual OpenCV/MediaPipe processing.
"""
import random
import math
from datetime import datetime
from ai.camera import camera_manager

# Per-student state tracking for smooth random-walk simulation
_student_states = {}

ATTENTION_STATES = ['attentive', 'attentive', 'attentive', 'distracted', 'sleeping', 'absent']
COGNITIVE_STATES = ['low', 'optimal', 'optimal', 'high']
EMOTIONS = ['neutral', 'neutral', 'happy', 'confused', 'bored', 'stressed']
HEAD_POSES = ['forward', 'forward', 'forward', 'left', 'right', 'down']


def _init_student(student_id):
    """Initialize a student's simulation state."""
    _student_states[student_id] = {
        'attention': random.uniform(55, 95),
        'cognitive': random.uniform(30, 70),
        'blink_rate': random.uniform(10, 20),
        'attention_state': 'attentive',
        'cognitive_state': 'optimal',
        'emotion': 'neutral',
        'head_pose': 'forward',
        'tick': 0,
    }


def _random_walk(value, step=5, min_val=0, max_val=100):
    """Smooth random walk within bounds."""
    delta = random.uniform(-step, step)
    return max(min_val, min(max_val, value + delta))


def simulate_student(student_id):
    """
    Returns a dict of simulated AI analysis for one student.
    Replace this function body with real OpenCV/MediaPipe processing.
    """
    if student_id not in _student_states:
        _init_student(student_id)

    state = _student_states[student_id]
    state['tick'] += 1

    # Smooth updates every tick
    state['attention'] = _random_walk(state['attention'], step=4)
    state['cognitive'] = _random_walk(state['cognitive'], step=3)
    state['blink_rate'] = _random_walk(state['blink_rate'], step=1, min_val=5, max_val=35)

    # Determine categorical states
    att = state['attention']
    cog = state['cognitive']

    if att >= 70:
        state['attention_state'] = 'attentive'
    elif att >= 45:
        state['attention_state'] = 'distracted'
    elif att >= 20:
        state['attention_state'] = 'sleeping'
    else:
        state['attention_state'] = 'absent'

    if cog < 35:
        state['cognitive_state'] = 'low'
    elif cog <= 65:
        state['cognitive_state'] = 'optimal'
    else:
        state['cognitive_state'] = 'high'

    # Emotion derived from attention + cognitive
    if att >= 70 and cog <= 65:
        state['emotion'] = random.choice(['neutral', 'happy', 'neutral'])
    elif att < 45:
        state['emotion'] = random.choice(['bored', 'distracted', 'neutral'])
    elif cog > 65:
        state['emotion'] = random.choice(['confused', 'stressed', 'confused'])
    else:
        state['emotion'] = 'neutral'

    # Head pose
    if att >= 70:
        state['head_pose'] = random.choice(['forward', 'forward', 'forward', 'left'])
    else:
        state['head_pose'] = random.choice(['left', 'right', 'down', 'forward'])

    return {
        'student_id': student_id,
        'attention_score': round(state['attention'], 1),
        'cognitive_load': round(state['cognitive'], 1),
        'attention_state': state['attention_state'],
        'cognitive_state': state['cognitive_state'],
        'emotion': state['emotion'],
        'blink_rate': round(state['blink_rate'], 1),
        'head_pose': state['head_pose'],
        'timestamp': datetime.utcnow().isoformat()
    }


def analyze_class(student_ids):
    """
    Runs simulation/real detection for all students and returns:
    - per_student: list of individual results
    - class_summary: aggregated class-level metrics
    """
    results = []
    
    # Check if we have real camera hardware
    if camera_manager.has_hardware:
        _, metrics = camera_manager.get_latest()
        if metrics:
            # We only have 1 camera, so we simulate everyone else,
            # but assign the real camera data to the first student in the list
            # for demo purposes
            real_student_id = student_ids[0] if student_ids else None
            for sid in student_ids:
                if sid == real_student_id:
                    # Update real metrics with the correct student ID
                    m = metrics.copy()
                    m['student_id'] = sid
                    results.append(m)
                else:
                    results.append(simulate_student(sid))
        else:
            # Hardware found but no frame yet
            results = [simulate_student(sid) for sid in student_ids]
    else:
        results = [simulate_student(sid) for sid in student_ids]

    if not results:
        return {'per_student': [], 'class_summary': {}}

    attention_scores = [r['attention_score'] for r in results]
    cognitive_loads = [r['cognitive_load'] for r in results]

    # Count states
    state_counts = {'attentive': 0, 'distracted': 0, 'sleeping': 0, 'absent': 0}
    cognitive_counts = {'low': 0, 'optimal': 0, 'high': 0}
    present_count = 0

    for r in results:
        state_counts[r['attention_state']] = state_counts.get(r['attention_state'], 0) + 1
        cognitive_counts[r['cognitive_state']] = cognitive_counts.get(r['cognitive_state'], 0) + 1
        if r.get('is_present', False):
            present_count += 1

    avg_attention = sum(attention_scores) / len(attention_scores)
    avg_cognitive = sum(cognitive_loads) / len(cognitive_loads)
    
    # Engagement index: 70% attention + 30% cognitive optimality
    engagement_index = (avg_attention * 0.7) + (max(0, 100 - abs(avg_cognitive - 50)*2) * 0.3)

    return {
        'per_student': results,
        'class_summary': {
            'avg_attention': round(avg_attention, 1),
            'avg_cognitive_load': round(avg_cognitive, 1),
            'engagement_index': round(engagement_index, 1),
            'total_students': len(results),
            'present_count': present_count,
            'state_counts': state_counts,
            'cognitive_counts': cognitive_counts,
            'timestamp': datetime.utcnow().isoformat()
        }
    }
