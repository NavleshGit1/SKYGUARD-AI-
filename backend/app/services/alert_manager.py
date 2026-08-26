"""
SkyGuard AI — Multi-Channel Alert Dispatch Manager
Blueprint §4 Component 8.4: WebSocket + Email SMTP + Twilio SMS + Slack Webhooks
Phase 8.3: Build Dispatch Connectors
"""
import time
import json
import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger("skyguard.alert_manager")


# ==============================================================================
# SMTP Email Dispatcher
# ==============================================================================
class SMTPDispatcher:
    """Sends HTML incident report emails via SMTP (Gmail / SendGrid / local relay)."""

    def __init__(self):
        self.host     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
        self.port     = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USERNAME",  "")
        self.password = os.getenv("SMTP_PASSWORD",  "")
        self.from_addr= os.getenv("SMTP_FROM_ADDR", "noreply@skyguard.ai")
        self.to_addrs = [a.strip() for a in os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",") if a.strip()]
        self.enabled  = bool(self.username and self.password and self.to_addrs)

    def send(self, subject: str, html_body: str, plain_body: str) -> Dict[str, Any]:
        if not self.enabled:
            logger.debug("[SMTP] Skipped — SMTP credentials not configured.")
            return {"channel": "EMAIL_SMTP", "status": "SKIPPED", "reason": "Credentials not configured"}

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.from_addr
            msg["To"]      = ", ".join(self.to_addrs)
            msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body,  "html"))

            with smtplib.SMTP(self.host, self.port, timeout=8) as server:
                server.ehlo()
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logger.info(f"[SMTP] Email sent to {self.to_addrs}")
            return {"channel": "EMAIL_SMTP", "status": "DELIVERED", "recipients": self.to_addrs}
        except Exception as exc:
            logger.error(f"[SMTP] Failed to send email: {exc}")
            return {"channel": "EMAIL_SMTP", "status": "FAILED", "error": str(exc)}


# ==============================================================================
# Twilio SMS Dispatcher
# ==============================================================================
class TwilioSMSDispatcher:
    """Sends SMS alerts via Twilio REST API for CRITICAL severity events."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token  = os.getenv("TWILIO_AUTH_TOKEN",  "")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "")
        self.to_numbers  = [n.strip() for n in os.getenv("ALERT_SMS_RECIPIENTS", "").split(",") if n.strip()]
        self.enabled     = bool(self.account_sid and self.auth_token and self.from_number and self.to_numbers)

    def send(self, message: str) -> Dict[str, Any]:
        if not self.enabled:
            logger.debug("[Twilio] Skipped — Twilio credentials not configured.")
            return {"channel": "SMS_TWILIO", "status": "SKIPPED", "reason": "Credentials not configured"}

        try:
            import urllib.request, urllib.parse, base64
            results = []
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            auth = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()

            for to_num in self.to_numbers:
                data = urllib.parse.urlencode({"From": self.from_number, "To": to_num, "Body": message}).encode()
                req  = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    body = json.loads(resp.read())
                    results.append({"to": to_num, "sid": body.get("sid"), "status": body.get("status")})

            logger.info(f"[Twilio] SMS sent to {self.to_numbers}")
            return {"channel": "SMS_TWILIO", "status": "DELIVERED", "results": results}
        except Exception as exc:
            logger.error(f"[Twilio] SMS failed: {exc}")
            return {"channel": "SMS_TWILIO", "status": "FAILED", "error": str(exc)}


# ==============================================================================
# Slack Webhook Dispatcher
# ==============================================================================
class SlackDispatcher:
    """Posts rich formatted incident blocks to a Slack channel via Incoming Webhook."""

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        self.enabled     = bool(self.webhook_url)

    def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            logger.debug("[Slack] Skipped — SLACK_WEBHOOK_URL not configured.")
            return {"channel": "SLACK_WEBHOOK", "status": "SKIPPED", "reason": "Webhook URL not configured"}

        try:
            import urllib.request
            data = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(self.webhook_url, data=data,
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                response_body = resp.read().decode()

            logger.info("[Slack] Alert posted successfully.")
            return {"channel": "SLACK_WEBHOOK", "status": "DELIVERED", "response": response_body}
        except Exception as exc:
            logger.error(f"[Slack] Webhook failed: {exc}")
            return {"channel": "SLACK_WEBHOOK", "status": "FAILED", "error": str(exc)}


# ==============================================================================
# ALERT MANAGER — Orchestrates all dispatch channels
# ==============================================================================
class AlertManager:
    """
    Intelligent Multi-Channel Alert Manager:
    1. Hysteresis / deduplication cooldown to prevent alarm fatigue
    2. Severity-based escalation routing
    3. Dispatches to: SMTP Email, Twilio SMS, Slack Webhook, WebSocket (handled by ingest.py)
    """

    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds   = cooldown_seconds
        self.last_alert_times: Dict[str, float] = {}
        self.smtp    = SMTPDispatcher()
        self.twilio  = TwilioSMSDispatcher()
        self.slack   = SlackDispatcher()

    def should_dispatch_alert(self, station_id: str, root_cause: str, severity_score: float) -> bool:
        """Deduplication filter: blocks alerts within cooldown window per station+fault_type."""
        if severity_score < 0.50:
            return False

        key  = f"{station_id}:{root_cause}"
        now  = time.time()
        last = self.last_alert_times.get(key, 0.0)

        # Critical alerts (≥ 0.85) use half the cooldown for rapid re-escalation
        effective_cooldown = self.cooldown_seconds / 2 if severity_score >= 0.85 else self.cooldown_seconds

        if (now - last) >= effective_cooldown:
            self.last_alert_times[key] = now
            return True
        return False

    def process_and_dispatch(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates hysteresis and dispatches to all configured channels."""
        station_id = alert_data.get("station_id", "AWS-UNKNOWN")
        root_cause = alert_data.get("root_cause", "UNKNOWN_FAULT")
        severity   = float(alert_data.get("severity_score", 0.0))

        should_send = self.should_dispatch_alert(station_id, root_cause, severity)

        dispatch_report = {
            "station_id":    station_id,
            "root_cause":    root_cause,
            "severity_score": severity,
            "dispatched":    should_send,
            "channels":      []
        }

        if not should_send:
            dispatch_report["reason"] = "Suppressed by hysteresis cooldown buffer."
            return dispatch_report

        # ── Format payloads ──────────────────────────────────────────────────

        # Slack Block Kit payload
        sev_pct     = int(severity * 100)
        color       = "#EF4444" if severity >= 0.75 else "#F59E0B"
        explanation = alert_data.get("explanation", "")
        ts          = alert_data.get("timestamp", datetime.now(timezone.utc).isoformat())
        severity_label = "🔴 CRITICAL" if severity >= 0.80 else ("🟡 WARNING" if severity >= 0.60 else "🟢 INFO")

        slack_payload = {
            "attachments": [{
                "color":  color,
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text",
                        "text": f"🚨 SkyGuard Alert — {station_id}"}},
                    {"type": "section", "fields": [
                        {"type": "mrkdwn", "text": f"*Fault Type:*\n{root_cause}"},
                        {"type": "mrkdwn", "text": f"*Severity:*\n{severity_label} ({sev_pct}%)"},
                        {"type": "mrkdwn", "text": f"*Station:*\n{station_id}"},
                        {"type": "mrkdwn", "text": f"*Timestamp:*\n{ts}"}
                    ]},
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*Diagnosis:*\n{explanation[:500]}"}},
                    {"type": "divider"}
                ]
            }]
        }

        # HTML Email body
        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#1e293b">
        <h2 style="color:{color}">🚨 SkyGuard AI — Sensor Anomaly Alert</h2>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
          <tr><td><b>Station ID</b></td><td>{station_id}</td></tr>
          <tr><td><b>Fault Type</b></td><td>{root_cause}</td></tr>
          <tr><td><b>Severity</b></td><td style="color:{color}"><b>{sev_pct}%</b></td></tr>
          <tr><td><b>Timestamp</b></td><td>{ts}</td></tr>
        </table>
        <h3>Diagnosis</h3>
        <p>{explanation}</p>
        <p style="color:#64748b;font-size:12px">— SkyGuard AI Autonomous Monitoring System</p>
        </body></html>"""

        plain_body = f"[SkyGuard Alert]\nStation: {station_id}\nFault: {root_cause}\nSeverity: {sev_pct}%\nTimestamp: {ts}\n\n{explanation}"
        email_subj = f"[SkyGuard {severity_label}] {root_cause} on {station_id}"

        # ── Dispatch to all channels ─────────────────────────────────────────

        # 1. Slack Webhook
        slack_result = self.slack.send(slack_payload)
        dispatch_report["channels"].append(slack_result)

        # 2. SMTP Email (always for any dispatchable alert)
        email_result = self.smtp.send(email_subj, html_body, plain_body)
        dispatch_report["channels"].append(email_result)

        # 3. Twilio SMS — only for CRITICAL severity (>= 0.80)
        if severity >= 0.80:
            sms_text   = (
                f"[SkyGuard CRITICAL] Station {station_id}: {root_cause}. "
                f"Severity {sev_pct}%. Immediate action required."
            )
            sms_result = self.twilio.send(sms_text)
            dispatch_report["channels"].append(sms_result)

        logger.info(f"[AlertManager] Alert dispatched for {station_id} | Severity {sev_pct}%")
        return dispatch_report

    def format_webhook_payload(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy compatibility: returns basic webhook payload dict."""
        sev = float(alert_data.get("severity_score", 0.0))
        return {
            "text": f"🚨 [SkyGuard AI Alert] Station {alert_data.get('station_id')} — {alert_data.get('root_cause')}",
            "severity_pct": int(sev * 100)
        }

    def format_email_summary(self, alert_data: Dict[str, Any]) -> Dict[str, str]:
        """Legacy compatibility: returns subject/body dict."""
        st_id      = alert_data.get("station_id")
        sev        = float(alert_data.get("severity_score", 0.0))
        root_cause = alert_data.get("root_cause")
        explanation= alert_data.get("explanation")
        return {
            "subject": f"[SkyGuard Advisory] Severity {int(sev * 100)}% Alert on Station {st_id}",
            "body":    f"Station: {st_id}\nFault: {root_cause}\nSeverity: {sev}\nDiagnosis: {explanation}"
        }


# Global Singleton
alert_manager = AlertManager(cooldown_seconds=120)
