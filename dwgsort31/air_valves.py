"""Manual valve edits remain separate from the original profile points."""
import math


def valve_values(distance, elevation, av, station, base_index=None):
    try:
        distance, elevation = float(distance), float(elevation)
    except (ValueError, TypeError):
        raise ValueError('누가거리와 관저고를 숫자로 입력해주세요.') from None
    if not math.isfinite(distance) or not math.isfinite(elevation) or distance < 0:
        raise ValueError('누가거리는 0 이상, 관저고는 유효한 숫자여야 합니다.')
    if not av.strip() or not station.strip():
        raise ValueError('AV 번호와 공기밸브 측점을 입력해주세요.')
    return dict(distance=distance, elevation=elevation, av=av.strip(), station=station.strip(), base_index=base_index)


def merge_valves(points, valves):
    rows = [dict(distance=d, elevation=e, av='', station='', valve_index=None) for d, e in points]
    attached = set()
    for i, record in enumerate(valves):
        value = valve_values(**record)
        base = value.pop('base_index')
        value['valve_index'] = i
        if base is None:
            rows.append(value)
        else:
            if not isinstance(base, int) or not 0 <= base < len(points) or base in attached:
                raise ValueError('기존 지점 연결이 잘못되었거나 중복되었습니다.')
            if points[base][0] != value['distance']:
                raise ValueError('기존 지점의 누가거리와 입력값이 다릅니다.')
            attached.add(base)
            rows[base] = value
    return sorted(rows, key=lambda row: row['distance'])
