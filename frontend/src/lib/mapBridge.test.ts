import type { Map as MapboxMap } from 'mapbox-gl';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { focusBounds, focusGeometry, registerMap } from './mapBridge';

/** Det enda av Mapbox-kartan som bryggan använder. */
function stubMap() {
  const fitBounds = vi.fn();
  return { map: { fitBounds } as unknown as MapboxMap, fitBounds };
}

afterEach(() => {
  registerMap(null);
});

describe('mapBridge', () => {
  it('fokus med registrerad karta anropar fitBounds med standardzoomtaket', () => {
    const { map, fitBounds } = stubMap();
    registerMap(map);

    focusBounds([18, 59, 18.1, 59.1]);

    expect(fitBounds).toHaveBeenCalledTimes(1);
    expect(fitBounds.mock.calls[0][0]).toEqual([
      [18, 59],
      [18.1, 59.1],
    ]);
    expect(fitBounds.mock.calls[0][1]).toMatchObject({ maxZoom: 16 });
  });

  it('fokus före load köas med sina options och utförs vid registrering', () => {
    focusGeometry({ type: 'Point', coordinates: [18, 59] }, { maxZoom: 12 });

    const { map, fitBounds } = stubMap();
    registerMap(map);

    expect(fitBounds).toHaveBeenCalledTimes(1);
    expect(fitBounds.mock.calls[0][0]).toEqual([
      [18, 59],
      [18, 59],
    ]);
    expect(fitBounds.mock.calls[0][1]).toMatchObject({ maxZoom: 12 });

    // Kön töms efter uppspelningen — en ny karta ska inte zooma dit igen
    registerMap(null);
    const again = stubMap();
    registerMap(again.map);
    expect(again.fitBounds).not.toHaveBeenCalled();
  });

  it('bara det senast begärda fokuset spelas upp', () => {
    focusBounds([1, 1, 2, 2], { maxZoom: 10 });
    focusBounds([3, 3, 4, 4]);

    const { map, fitBounds } = stubMap();
    registerMap(map);

    expect(fitBounds).toHaveBeenCalledTimes(1);
    expect(fitBounds.mock.calls[0][0]).toEqual([
      [3, 3],
      [4, 4],
    ]);
    expect(fitBounds.mock.calls[0][1]).toMatchObject({ maxZoom: 16 });
  });

  it('ingen effekt, och inget köas, utan geometri eller med ogiltiga tal', () => {
    focusGeometry(null);
    focusGeometry(undefined);
    focusBounds([Number.NaN, 59, 18, 60]);

    const { map, fitBounds } = stubMap();
    registerMap(map);
    expect(fitBounds).not.toHaveBeenCalled();
  });
});
