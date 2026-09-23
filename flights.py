"""Flight metasearch endpoints: one-way/round search, Nomad multi-city, calendar, trend, drops, popular, nearby."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from lib.pricing import cheapest, compose, fetch_legs, parse_date, refs
from models.travel import (
    CalendarPoint,
    DropOut,
    ItineraryOut,
    NearbySuggestion,
    NomadAlternate,
    NomadIn,
    NomadOut,
    NomadSegment,
    PopularRoute,
    SearchIn,
    SearchOut,
    TrendOut,
)

router = APIRouter()

POPULAR = [
    ("JFK", "CDG"), ("LHR", "HND"), ("CDG", "BKK"), ("SFO", "NRT"),
    ("IST", "BKK"), ("DXB", "LHR"), ("LAX", "SYD"), ("SIN", "JFK"),
]
DROP_DESTS = ["CDG", "HND", "SIN", "BKK", "DXB", "JFK", "LHR", "FCO", "BCN", "LAX"]


@router.post("/flights/search", response_model=SearchOut)
async def search_flights(q: SearchIn):
    apts, als = await refs()
    if q.origin not in apts:
        raise HTTPException(status_code=404, detail=f"unknown origin {q.origin}")
    if q.destination not in apts:
        raise HTTPException(status_code=404, detail=f"unknown destination {q.destination}")
    if q.origin == q.destination:
        raise HTTPException(status_code=422, detail="origin and destination must differ")
    pax = q.adults + 0.75 * q.children + 0.1 * q.infants
    lf, lt = await fetch_legs(q.origin, q.destination)
    outbound = compose(lf, lt, q.destination, q.date, q.cabin, pax, apts, als)
    inbound: List[ItineraryOut] = []
    if q.return_date:
        lf2, lt2 = await fetch_legs(q.destination, q.origin)
        inbound = compose(lf2, lt2, q.origin, q.return_date, q.cabin, pax, apts, als)
    return SearchOut(
        origin=q.origin,
        destination=q.destination,
        date=q.date,
        return_date=q.return_date,
        outbound=outbound,
        inbound=inbound,
    )


@router.post("/flights/nomad", response_model=NomadOut)
async def nomad_search(q: NomadIn):
    apts, als = await refs()
    for s in q.stops:
        if s.iata not in apts:
            raise HTTPException(status_code=404, detail=f"unknown airport {s.iata}")
    segments: List[NomadSegment] = []
    for i in range(len(q.stops) - 1):
        a, b = q.stops[i], q.stops[i + 1]
        if a.iata == b.iata:
            raise HTTPException(status_code=422, detail="consecutive stops must differ")
        lf, lt = await fetch_legs(a.iata, b.iata)
        # stops[i].date = the date you depart FROM that city (spec timeline semantics)
        opts = compose(lf, lt, b.iata, a.date, q.cabin, 1.0, apts, als, limit=4)
        if not opts:
            raise HTTPException(status_code=404, detail=f"no flights {a.iata}→{b.iata} on {a.date}")
        segments.append(
            NomadSegment(
                from_iata=a.iata,
                from_city=apts[a.iata]["city"],
                to_iata=b.iata,
                to_city=apts[b.iata]["city"],
                date=a.date,
                options=opts,
            )
        )
    total = round(sum(s.options[0].price for s in segments), 2)
    total_dur = sum(s.options[0].duration_min for s in segments)

    alternates: List[NomadAlternate] = []
    priciest = max(range(len(segments)), key=lambda i: segments[i].options[0].price)
    today = datetime.now(timezone.utc).date()
    for shift in (-1, 1):
        d = parse_date(q.stops[priciest].date) + timedelta(days=shift)
        if d < today:
            continue
        date_iso = d.strftime("%Y-%m-%d")
        a, b = q.stops[priciest], q.stops[priciest + 1]
        lf, lt = await fetch_legs(a.iata, b.iata)
        opts = compose(lf, lt, b.iata, date_iso, q.cabin, 1.0, apts, als, limit=1)
        if opts and segments[priciest].options[0].price - opts[0].price >= max(25.0, total * 0.04):
            segs = [s.model_copy(deep=True) for s in segments]
            segs[priciest] = segs[priciest].model_copy(update={"date": date_iso, "options": opts})
            alt_total = round(sum(s.options[0].price for s in segs), 2)
            alternates.append(
                NomadAlternate(
                    label=f"Shift {a.iata}→{b.iata} to {date_iso}",
                    segments=segs,
                    total=alt_total,
                    savings=round(total - alt_total, 2),
                )
            )
    alternates.sort(key=lambda x: x.savings, reverse=True)
    return NomadOut(segments=segments, total=total, total_duration_min=total_dur, alternates=alternates[:2])


@router.get("/flights/calendar", response_model=List[CalendarPoint])
async def price_calendar(origin: str, destination: str, month: str, cabin: str = "economy"):
    try:
        year, mon = int(month.split("-")[0]), int(month.split("-")[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    import calendar as _cal

    last_day = _cal.monthrange(year, mon)[1]
    lf, lt = await fetch_legs(origin, destination)
    today = datetime.now(timezone.utc).date()
    d = max(datetime(year, mon, 1).date(), today)
    end = datetime(year, mon, last_day).date()
    pts: List[CalendarPoint] = []
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        p = cheapest(lf, lt, destination, ds, cabin)
        if p is not None:
            pts.append(CalendarPoint(date=ds, price=p))
        d += timedelta(days=1)
    return pts


@router.get("/flights/trend", response_model=TrendOut)
async def price_trend(origin: str, destination: str, date: str, cabin: str = "economy"):
    lf, lt = await fetch_legs(origin, destination)
    today = datetime.now(timezone.utc).date()
    pts: List[CalendarPoint] = []
    for i in range(0, 60):
        ds = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        p = cheapest(lf, lt, destination, ds, cabin)
        if p is not None:
            pts.append(CalendarPoint(date=ds, price=p))
    if not pts:
        raise HTTPException(status_code=404, detail="no route")
    req = next((p.price for p in pts if p.date == date), None)
    if req is None:
        req = cheapest(lf, lt, destination, date, cabin)
        if req is None:
            req = pts[-1].price
    prices = sorted(p.price for p in pts)
    mn, med = prices[0], prices[len(prices) // 2]
    best = min(pts, key=lambda p: p.price)
    if req <= mn * 1.03:
        verdict, change = "Book now — you're at the 60-day low for this route.", 0.0
    elif req >= med * 1.12:
        change = round((req - med) / req * 100, 1)
        verdict = f"Wait — fares on this route typically dip ~{change:.0f}% below today's price."
    else:
        change = round((req - mn) / req * 100, 1)
        verdict = "Fair price — this window is stable for this route."
    return TrendOut(points=pts, verdict=verdict, expected_change=change, best_date=best.date)


@router.get("/flights/drops", response_model=List[DropOut])
async def price_drops(home: Optional[str] = None):
    apts, _ = await refs()
    today = datetime.now(timezone.utc).date()
    origin = home if home in apts else "JFK"
    dests = [d for d in dict.fromkeys(DROP_DESTS) if d != origin][:10]
    results: List[DropOut] = []
    for dest in dests:
        lf, lt = await fetch_legs(origin, dest)
        # near window (min over ~4 weeks out) vs the 8-11 week baseline: same urgency regime,
        # so a >=20% gap is a genuine simulated "drop", not last-minute pricing noise
        near = [
            (i, cheapest(lf, lt, dest, (today + timedelta(days=i)).strftime("%Y-%m-%d"), "economy"))
            for i in range(21, 49, 3)
        ]
        was_list = [
            cheapest(lf, lt, dest, (today + timedelta(days=i)).strftime("%Y-%m-%d"), "economy", with_sales=False)
            for i in range(21, 49, 3)
        ]
        # "was" = the regular (no-sale) fare floor for the same dates, so a drop is a genuine sale
        was_list = [p for p in was_list if p is not None]
        near_valid = [(i, p) for i, p in near if p is not None]
        if not near_valid or not was_list:
            continue
        i_best, now_p = min(near_valid, key=lambda x: x[1])
        was = round(sum(was_list) / len(was_list), 2)
        percent = round((1 - now_p / was) * 100, 1)
        if percent >= 20:
            results.append(
                DropOut(
                    origin=origin,
                    origin_city=apts[origin]["city"],
                    destination=dest,
                    dest_city=apts[dest]["city"],
                    price_now=now_p,
                    price_was=was,
                    percent=percent,
                    date=(today + timedelta(days=i_best)).strftime("%Y-%m-%d"),
                )
            )
    results.sort(key=lambda x: x.percent, reverse=True)
    return results[:6]


@router.get("/flights/popular", response_model=List[PopularRoute])
async def popular_routes():
    apts, _ = await refs()
    ds = (datetime.now(timezone.utc).date() + timedelta(days=21)).strftime("%Y-%m-%d")
    out: List[PopularRoute] = []
    for o, d in POPULAR:
        if o not in apts or d not in apts:
            continue
        lf, lt = await fetch_legs(o, d)
        p = cheapest(lf, lt, d, ds, "economy")
        if p is not None:
            out.append(
                PopularRoute(origin=o, origin_city=apts[o]["city"], destination=d, dest_city=apts[d]["city"], price=p)
            )
    return out


@router.get("/flights/nearby", response_model=List[NearbySuggestion])
async def nearby_airports(origin: str, destination: str, date: str, cabin: str = "economy"):
    apts, _ = await refs()
    if origin not in apts or destination not in apts:
        return []
    lf, lt = await fetch_legs(origin, destination)
    base = cheapest(lf, lt, destination, date, cabin)
    if base is None:
        return []
    o_city, d_city = apts[origin]["city_code"], apts[destination]["city_code"]
    alts = [(i, "origin") for i, a in apts.items() if a["city_code"] == o_city and i != origin]
    alts += [(i, "destination") for i, a in apts.items() if a["city_code"] == d_city and i != destination]
    out: List[NearbySuggestion] = []
    for iata, kind in alts:
        if kind == "origin":
            lf2, lt2 = await fetch_legs(iata, destination)
            p = cheapest(lf2, lt2, destination, date, cabin)
        else:
            lf2, lt2 = await fetch_legs(origin, iata)
            p = cheapest(lf2, lt2, iata, date, cabin)
        if p is not None and base - p >= 15:
            out.append(
                NearbySuggestion(
                    iata=iata,
                    name=apts[iata]["name"],
                    city=apts[iata]["city"],
                    kind=kind,
                    price=p,
                    base_price=base,
                    save=round(base - p, 2),
                )
            )
    out.sort(key=lambda x: x.save, reverse=True)
    return out[:3]
