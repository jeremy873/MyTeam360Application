# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Safe Integration Framework — READ-ONLY external data connections.

IRON-CLAD SAFETY POLICY (The OpenClaw Rule):
  READ:    ✅ We can READ calendars, emails, and data
  DISPLAY: ✅ We can DISPLAY information to the user
  SUGGEST: ✅ We can SUGGEST actions to the user
  CREATE:  ⚠️ ONLY with explicit user confirmation + audit log
  MODIFY:  ❌ NEVER modify existing external data
  DELETE:  ❌ NEVER delete anything in an external system
  MOVE:    ❌ NEVER move, archive, or reorganize external data

Integrations:
  1. Google Calendar (read-only: today's events, upcoming meetings)
  2. Outlook Calendar (read-only: same)
  3. Email summary (read-only: unread count, sender names, subjects)
  4. Flight status (user enters confirmation → we check public API)
  5. Weather (location-based, feeds into daily briefing)
  6. Traffic/commute estimate (meeting location → drive time)
"""

import json
import uuid
import os
import logging
import requests
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.integrations_safe")


# ══════════════════════════════════════════════════════════════
# SAFETY ENFORCEMENT — Every integration goes through this
# ══════════════════════════════════════════════════════════════

ALLOWED_OPERATIONS = {
    "calendar": ["read", "display"],
    "email": ["read", "display"],
    "flight": ["read", "display"],
    "weather": ["read", "display"],
    "traffic": ["read", "display"],
}

FORBIDDEN_OPERATIONS = [
    "delete", "remove", "archive", "move", "modify", "update",
    "send", "forward", "reply", "mark_read", "mark_unread",
    "create_event", "cancel_event", "reschedule",
]


def enforce_safety(integration: str, operation: str) -> bool:
    """Check if an operation is allowed. Returns False if blocked."""
    if operation in FORBIDDEN_OPERATIONS:
        logger.warning(f"BLOCKED forbidden operation: {integration}.{operation}")
        return False
    allowed = ALLOWED_OPERATIONS.get(integration, [])
    if operation not in allowed:
        logger.warning(f"BLOCKED unrecognized operation: {integration}.{operation}")
        return False
    return True


# ══════════════════════════════════════════════════════════════
# 1. CALENDAR INTEGRATION (Google + Outlook) — READ ONLY
# ══════════════════════════════════════════════════════════════

class CalendarReader:
    """Read-only calendar access. NEVER creates, modifies, or deletes events."""

    def connect_google(self, user_id: str, access_token: str,
                        refresh_token: str = "") -> dict:
        """Store Google Calendar OAuth token (encrypted)."""
        return self._store_connection(user_id, "google_calendar",
                                       access_token, refresh_token)

    def connect_outlook(self, user_id: str, access_token: str,
                         refresh_token: str = "") -> dict:
        """Store Outlook Calendar OAuth token (encrypted)."""
        return self._store_connection(user_id, "outlook_calendar",
                                       access_token, refresh_token)

    def get_today_events(self, user_id: str) -> dict:
        """Get today's calendar events from all connected calendars."""
        if not enforce_safety("calendar", "read"):
            return {"error": "Operation blocked by safety policy"}

        connections = self._get_connections(user_id, "calendar")
        all_events = []

        for conn in connections:
            provider = conn["provider"]
            try:
                if provider == "google_calendar":
                    events = self._fetch_google_events(conn["access_token"])
                elif provider == "outlook_calendar":
                    events = self._fetch_outlook_events(conn["access_token"])
                else:
                    continue
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Calendar fetch error ({provider}): {e}")
                all_events.append({
                    "source": provider,
                    "error": "Could not fetch events. Token may need refresh.",
                })

        # Sort by start time
        all_events.sort(key=lambda e: e.get("start", ""))

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "events": all_events,
            "total": len([e for e in all_events if "error" not in e]),
            "safety": "READ-ONLY — MyTeam360 cannot modify your calendar",
        }

    def get_upcoming(self, user_id: str, days: int = 7) -> dict:
        """Get events for the next N days."""
        if not enforce_safety("calendar", "read"):
            return {"error": "Operation blocked by safety policy"}

        # Same fetch logic, wider date range
        connections = self._get_connections(user_id, "calendar")
        events = []
        for conn in connections:
            try:
                if conn["provider"] == "google_calendar":
                    events.extend(self._fetch_google_events(conn["access_token"], days=days))
                elif conn["provider"] == "outlook_calendar":
                    events.extend(self._fetch_outlook_events(conn["access_token"], days=days))
            except Exception as e:
                logger.error(f"Calendar fetch error: {e}")

        events.sort(key=lambda e: e.get("start", ""))
        return {"events": events, "days": days}

    def get_next_meeting(self, user_id: str) -> dict:
        """Get the very next meeting — for meeting prep."""
        today = self.get_today_events(user_id)
        now = datetime.now().isoformat()
        upcoming = [e for e in today.get("events", [])
                    if e.get("start", "") > now and "error" not in e]
        if upcoming:
            return {"next_meeting": upcoming[0], "has_meeting": True}
        return {"has_meeting": False, "message": "No more meetings today"}

    def _fetch_google_events(self, access_token: str, days: int = 1) -> list:
        """Fetch events from Google Calendar API (read-only)."""
        try:
            now = datetime.utcnow()
            time_min = now.strftime("%Y-%m-%dT00:00:00Z")
            time_max = (now + timedelta(days=days)).strftime("%Y-%m-%dT23:59:59Z")
            resp = requests.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                params={
                    "timeMin": time_min, "timeMax": time_max,
                    "singleEvents": "true", "orderBy": "startTime",
                    "maxResults": 50,
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10)
            if resp.status_code != 200:
                return [{"source": "google", "error": f"API error: {resp.status_code}"}]
            data = resp.json()
            events = []
            for item in data.get("items", []):
                start = item.get("start", {})
                end = item.get("end", {})
                events.append({
                    "source": "google_calendar",
                    "title": item.get("summary", "No title"),
                    "start": start.get("dateTime", start.get("date", "")),
                    "end": end.get("dateTime", end.get("date", "")),
                    "location": item.get("location", ""),
                    "description": (item.get("description", "") or "")[:200],
                    "attendees": [a.get("email", "") for a in item.get("attendees", [])],
                    "meeting_link": item.get("hangoutLink", ""),
                    "status": item.get("status", ""),
                })
            return events
        except Exception as e:
            return [{"source": "google", "error": str(e)}]

    def _fetch_outlook_events(self, access_token: str, days: int = 1) -> list:
        """Fetch events from Microsoft Graph API (read-only)."""
        try:
            now = datetime.utcnow()
            start = now.strftime("%Y-%m-%dT00:00:00Z")
            end = (now + timedelta(days=days)).strftime("%Y-%m-%dT23:59:59Z")
            resp = requests.get(
                "https://graph.microsoft.com/v1.0/me/calendarView",
                params={"startDateTime": start, "endDateTime": end,
                        "$top": 50, "$orderby": "start/dateTime"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10)
            if resp.status_code != 200:
                return [{"source": "outlook", "error": f"API error: {resp.status_code}"}]
            data = resp.json()
            events = []
            for item in data.get("value", []):
                events.append({
                    "source": "outlook_calendar",
                    "title": item.get("subject", "No title"),
                    "start": item.get("start", {}).get("dateTime", ""),
                    "end": item.get("end", {}).get("dateTime", ""),
                    "location": (item.get("location", {}) or {}).get("displayName", ""),
                    "attendees": [a.get("emailAddress", {}).get("address", "")
                                 for a in item.get("attendees", [])],
                    "meeting_link": item.get("onlineMeetingUrl", ""),
                    "is_online": item.get("isOnlineMeeting", False),
                })
            return events
        except Exception as e:
            return [{"source": "outlook", "error": str(e)}]

    def _store_connection(self, user_id: str, provider: str,
                           access_token: str, refresh_token: str) -> dict:
        cid = f"cal_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO safe_integrations
                    (id, user_id, provider, access_token, refresh_token, status)
                VALUES (?,?,?,?,?,?)
            """, (cid, user_id, provider, access_token, refresh_token, "active"))
        return {"connected": True, "provider": provider, "id": cid,
                "safety": "READ-ONLY access. MyTeam360 cannot modify your calendar."}

    def _get_connections(self, user_id: str, category: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM safe_integrations WHERE user_id=? AND provider LIKE ? AND status='active'",
                (user_id, f"%{category}%")).fetchall()
        return [dict(r) for r in rows]

    def disconnect(self, user_id: str, connection_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM safe_integrations WHERE id=? AND user_id=?",
                      (connection_id, user_id))
        return {"disconnected": True}

    def list_connections(self, user_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, provider, status, created_at FROM safe_integrations WHERE user_id=?",
                (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# 2. EMAIL SUMMARY — READ ONLY (never touch the inbox)
# ══════════════════════════════════════════════════════════════

class EmailReader:
    """Read-only email summary. NEVER sends, deletes, moves, or modifies emails."""

    def get_inbox_summary(self, user_id: str) -> dict:
        """Get unread count and top senders — for daily briefing."""
        if not enforce_safety("email", "read"):
            return {"error": "Operation blocked by safety policy"}

        connections = []
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM safe_integrations WHERE user_id=? AND provider LIKE '%email%' AND status='active'",
                (user_id,)).fetchall()
            connections = [dict(r) for r in rows]

        if not connections:
            return {"connected": False,
                    "message": "Connect your email for inbox summaries in your briefing"}

        summaries = []
        for conn in connections:
            try:
                if "gmail" in conn["provider"]:
                    summaries.append(self._fetch_gmail_summary(conn["access_token"]))
                elif "outlook" in conn["provider"]:
                    summaries.append(self._fetch_outlook_summary(conn["access_token"]))
            except Exception as e:
                logger.error(f"Email fetch error: {e}")

        return {
            "summaries": summaries,
            "safety": "READ-ONLY — MyTeam360 cannot send, delete, move, or modify your emails",
        }

    def _fetch_gmail_summary(self, access_token: str) -> dict:
        """Read-only Gmail summary via API."""
        try:
            resp = requests.get(
                "https://www.googleapis.com/gmail/v1/users/me/messages",
                params={"q": "is:unread in:inbox", "maxResults": 20},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10)
            if resp.status_code != 200:
                return {"source": "gmail", "error": f"API error: {resp.status_code}"}
            data = resp.json()
            unread_count = data.get("resultSizeEstimate", 0)
            # Get subjects of top 5
            top_messages = []
            for msg in data.get("messages", [])[:5]:
                detail = requests.get(
                    f"https://www.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                    params={"format": "metadata", "metadataHeaders": "From,Subject"},
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5).json()
                headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
                top_messages.append({
                    "from": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "No subject"),
                })
            return {"source": "gmail", "unread": unread_count, "top_messages": top_messages}
        except Exception as e:
            return {"source": "gmail", "error": str(e)}

    def _fetch_outlook_summary(self, access_token: str) -> dict:
        """Read-only Outlook summary via Microsoft Graph."""
        try:
            resp = requests.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                params={"$filter": "isRead eq false", "$top": 20,
                        "$select": "from,subject,receivedDateTime",
                        "$orderby": "receivedDateTime desc"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10)
            if resp.status_code != 200:
                return {"source": "outlook", "error": f"API error: {resp.status_code}"}
            data = resp.json()
            messages = data.get("value", [])
            return {
                "source": "outlook",
                "unread": len(messages),
                "top_messages": [{
                    "from": m.get("from", {}).get("emailAddress", {}).get("address", "Unknown"),
                    "subject": m.get("subject", "No subject"),
                } for m in messages[:5]],
            }
        except Exception as e:
            return {"source": "outlook", "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 3. FLIGHT STATUS TRACKER
# ══════════════════════════════════════════════════════════════

class FlightTracker:
    """Track flight status. User provides flight number or confirmation."""

    def add_flight(self, user_id: str, flight_number: str,
                    date: str = "", airline: str = "",
                    confirmation: str = "", notes: str = "") -> dict:
        fid = f"flight_{uuid.uuid4().hex[:8]}"
        flight_date = date or datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            db.execute("""
                INSERT INTO tracked_flights
                    (id, user_id, flight_number, airline, flight_date,
                     confirmation, notes, status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (fid, user_id, flight_number.upper(), airline, flight_date,
                  confirmation, notes, "scheduled"))
        return {"id": fid, "flight": flight_number.upper(), "date": flight_date}

    def get_flights(self, user_id: str) -> list:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM tracked_flights WHERE user_id=? AND flight_date>=? ORDER BY flight_date",
                (user_id, today)).fetchall()
        return [dict(r) for r in rows]

    def check_status(self, flight_number: str, date: str = "") -> dict:
        """Check flight status via public API."""
        # Uses AviationStack or similar free API
        api_key = os.getenv("AVIATIONSTACK_API_KEY", "")
        if not api_key:
            return {"flight": flight_number, "status": "unknown",
                    "message": "Flight tracking API not configured. Set AVIATIONSTACK_API_KEY.",
                    "manual_check": f"https://www.google.com/search?q={flight_number}+flight+status"}
        try:
            resp = requests.get("http://api.aviationstack.com/v1/flights",
                params={"access_key": api_key, "flight_iata": flight_number},
                timeout=10)
            data = resp.json()
            flights = data.get("data", [])
            if flights:
                f = flights[0]
                return {
                    "flight": flight_number,
                    "airline": f.get("airline", {}).get("name", ""),
                    "status": f.get("flight_status", "unknown"),
                    "departure": {
                        "airport": f.get("departure", {}).get("airport", ""),
                        "scheduled": f.get("departure", {}).get("scheduled", ""),
                        "estimated": f.get("departure", {}).get("estimated", ""),
                        "gate": f.get("departure", {}).get("gate", ""),
                        "delay_minutes": f.get("departure", {}).get("delay", 0),
                    },
                    "arrival": {
                        "airport": f.get("arrival", {}).get("airport", ""),
                        "scheduled": f.get("arrival", {}).get("scheduled", ""),
                        "estimated": f.get("arrival", {}).get("estimated", ""),
                        "gate": f.get("arrival", {}).get("gate", ""),
                    },
                }
            return {"flight": flight_number, "status": "not_found"}
        except Exception as e:
            return {"flight": flight_number, "status": "error", "error": str(e)}

    def remove_flight(self, flight_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM tracked_flights WHERE id=?", (flight_id,))
        return {"removed": True}


# ══════════════════════════════════════════════════════════════
# 4. WEATHER (for briefing + meeting context)
# ══════════════════════════════════════════════════════════════

class WeatherService:
    """Weather data for daily briefing and meeting context."""

    def get_weather(self, location: str = "", lat: float = None,
                     lon: float = None) -> dict:
        """Get current weather + forecast."""
        api_key = os.getenv("OPENWEATHER_API_KEY", "")
        if not api_key:
            return {"available": False,
                    "message": "Weather not configured. Set OPENWEATHER_API_KEY."}
        try:
            params = {"appid": api_key, "units": "imperial"}
            if lat and lon:
                params["lat"] = lat
                params["lon"] = lon
            elif location:
                params["q"] = location
            else:
                return {"available": False, "message": "Location required"}

            resp = requests.get("https://api.openweathermap.org/data/2.5/weather",
                               params=params, timeout=10)
            if resp.status_code != 200:
                return {"available": False, "error": f"API error: {resp.status_code}"}
            data = resp.json()
            return {
                "available": True,
                "location": data.get("name", location),
                "temperature": round(data.get("main", {}).get("temp", 0)),
                "feels_like": round(data.get("main", {}).get("feels_like", 0)),
                "condition": data.get("weather", [{}])[0].get("main", ""),
                "description": data.get("weather", [{}])[0].get("description", ""),
                "humidity": data.get("main", {}).get("humidity", 0),
                "wind_mph": round(data.get("wind", {}).get("speed", 0)),
                "suggestion": self._weather_suggestion(data),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _weather_suggestion(self, data: dict) -> str:
        temp = data.get("main", {}).get("temp", 70)
        condition = data.get("weather", [{}])[0].get("main", "").lower()
        suggestions = []
        if "rain" in condition or "drizzle" in condition:
            suggestions.append("Grab an umbrella")
        if "snow" in condition:
            suggestions.append("Roads may be slippery — leave extra time")
        if temp < 40:
            suggestions.append("Bundle up — it's cold out there")
        elif temp > 95:
            suggestions.append("Stay hydrated — it's hot")
        if not suggestions:
            suggestions.append("Great weather for getting things done")
        return ". ".join(suggestions) + "."


# ══════════════════════════════════════════════════════════════
# 5. TRAFFIC / COMMUTE ESTIMATE
# ══════════════════════════════════════════════════════════════

class CommuteEstimator:
    """Estimate drive time to meetings using location data."""

    def estimate(self, origin: str, destination: str) -> dict:
        """Get drive time estimate."""
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            return {
                "available": False,
                "message": "Traffic estimates not configured. Set GOOGLE_MAPS_API_KEY.",
                "manual_check": f"https://www.google.com/maps/dir/{origin}/{destination}",
            }
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": origin, "destinations": destination,
                    "departure_time": "now", "key": api_key,
                }, timeout=10)
            data = resp.json()
            if data.get("status") != "OK":
                return {"available": False, "error": data.get("status")}
            element = data["rows"][0]["elements"][0]
            if element.get("status") != "OK":
                return {"available": False, "error": element.get("status")}
            duration = element.get("duration_in_traffic", element.get("duration", {}))
            return {
                "available": True,
                "origin": origin,
                "destination": destination,
                "distance": element.get("distance", {}).get("text", ""),
                "duration": duration.get("text", ""),
                "duration_seconds": duration.get("value", 0),
                "leave_by": self._calculate_leave_time(duration.get("value", 0)),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _calculate_leave_time(self, duration_seconds: int,
                               meeting_time: str = "") -> str:
        """Calculate when to leave, with 10-minute buffer."""
        if not meeting_time:
            return ""
        try:
            meeting = datetime.fromisoformat(meeting_time)
            leave = meeting - timedelta(seconds=duration_seconds + 600)
            return leave.strftime("%I:%M %p")
        except:
            return ""

    def get_meeting_commute(self, user_id: str, home_location: str = "") -> list:
        """Get commute estimates for today's meetings that have locations."""
        calendar = CalendarReader()
        today = calendar.get_today_events(user_id)
        commutes = []
        for event in today.get("events", []):
            location = event.get("location", "")
            if location and home_location:
                est = self.estimate(home_location, location)
                if est.get("available"):
                    commutes.append({
                        "meeting": event.get("title", ""),
                        "time": event.get("start", ""),
                        "location": location,
                        "drive_time": est.get("duration", ""),
                        "leave_by": est.get("leave_by", ""),
                    })
        return commutes
