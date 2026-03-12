# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
MyTeam360 — Expanded Test Suite
Tests every feature area: CRM, Invoicing, Tasks, Social Media, Whiteboard,
Goals, Expenses, Email, Competitors, Client Portal, Setup Concierge,
Education Themes, CRM Customization, Launch Fixes, Biz Upgrades
"""

import pytest
import json
import os
import sys

# Ensure clean DB for each test run
DB_PATH = "data/myteam360.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

os.environ.setdefault("MT360_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXk=")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")

from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c

@pytest.fixture
def auth_headers(client):
    """Register + login, return auth headers."""
    client.post("/api/auth/register", json={
        "email": "testuser@test.com", "password": "TestPass123!", "name": "Test User"})
    resp = client.post("/api/auth/login", json={
        "email": "testuser@test.com", "password": "TestPass123!"})
    data = resp.get_json()
    token = data.get("token", "")
    cookie = resp.headers.get("Set-Cookie", "")
    # Return session cookie approach
    return {}


def _login(client, email="admin@localhost", password="admin123"):
    """Helper to login and get session."""
    client.post("/api/auth/login", json={"email": email, "password": password})


# ═══════════════════════════════════════════════════════════════
# CRM TESTS
# ═══════════════════════════════════════════════════════════════

class TestCRM:
    def test_create_contact(self):
        from core.crm import CRMManager
        crm = CRMManager()
        c = crm.create_contact("u1", "Alice Smith", email="alice@test.com",
                                company="TestCorp", title="CEO", tags=["vip"])
        assert c["id"].startswith("contact_")
        assert c["name"] == "Alice Smith"

    def test_get_contact(self):
        from core.crm import CRMManager
        crm = CRMManager()
        c = crm.create_contact("u1", "Bob Jones", email="bob@test.com")
        fetched = crm.get_contact(c["id"])
        assert fetched is not None
        assert fetched["name"] == "Bob Jones"
        assert fetched["email"] == "bob@test.com"

    def test_list_contacts(self):
        from core.crm import CRMManager
        crm = CRMManager()
        crm.create_contact("u2", "Contact A")
        crm.create_contact("u2", "Contact B")
        contacts = crm.list_contacts("u2")
        assert len(contacts) >= 2

    def test_search_contacts(self):
        from core.crm import CRMManager
        crm = CRMManager()
        crm.create_contact("u3", "Unique Name XYZ", company="UniqueCompany")
        results = crm.list_contacts("u3", search="Unique")
        assert len(results) >= 1

    def test_update_contact(self):
        from core.crm import CRMManager
        crm = CRMManager()
        c = crm.create_contact("u1", "Update Me")
        result = crm.update_contact(c["id"], name="Updated Name", phone="555-1234")
        assert result["updated"]

    def test_delete_contact(self):
        from core.crm import CRMManager
        crm = CRMManager()
        c = crm.create_contact("u1", "Delete Me")
        result = crm.delete_contact(c["id"])
        assert result["deleted"]
        assert crm.get_contact(c["id"]) is None

    def test_create_deal(self):
        from core.crm import CRMManager
        crm = CRMManager()
        d = crm.create_deal("u1", "Big Deal", value=50000, stage="qualified")
        assert d["id"].startswith("deal_")
        assert d["value"] == 50000
        assert d["stage"] == "qualified"

    def test_move_deal(self):
        from core.crm import CRMManager
        crm = CRMManager()
        d = crm.create_deal("u1", "Moving Deal", stage="lead")
        result = crm.move_deal(d["id"], "proposal")
        assert result["updated"]

    def test_log_activity(self):
        from core.crm import CRMManager
        crm = CRMManager()
        a = crm.log_activity("u1", "call", "Intro call with prospect")
        assert a["id"].startswith("act_")
        assert a["type"] == "call"

    def test_create_company(self):
        from core.crm import CRMManager
        crm = CRMManager()
        c = crm.create_company("u1", "Acme Corp", domain="acme.com", industry="Tech")
        assert c["name"] == "Acme Corp"

    def test_pipeline_dashboard(self):
        from core.crm import CRMManager
        crm = CRMManager()
        crm.create_deal("u4", "Pipeline Test", value=10000)
        pipeline = crm.get_pipeline("u4")
        assert "pipeline_value" in pipeline
        assert "win_rate" in pipeline
        assert "total_contacts" in pipeline

    def test_build_contact_context(self):
        from core.crm import CRMManager
        crm = CRMManager()
        c = crm.create_contact("u5", "Context Test", email="ctx@test.com", company="CtxCorp")
        crm.log_activity("u5", "email", "Sent proposal", contact_id=c["id"])
        ctx = crm.build_contact_context(c["id"])
        assert "Context Test" in ctx
        assert "CtxCorp" in ctx


# ═══════════════════════════════════════════════════════════════
# INVOICING TESTS
# ═══════════════════════════════════════════════════════════════

class TestInvoicing:
    def test_set_business_profile(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        p = im.set_business_profile("u1", "Test Biz", email="test@biz.com",
                                     default_payment_terms=15)
        assert p["business_name"] == "Test Biz"
        assert p["default_payment_terms"] == 15

    def test_create_invoice(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        inv = im.create_invoice("u10", "Client ABC", line_items=[
            {"description": "Service A", "quantity": 2, "unit_price": 500},
            {"description": "Service B", "quantity": 1, "unit_price": 1000},
        ])
        assert inv["invoice_number"] == "INV-0001"
        assert inv["total"] == 2000.0

    def test_invoice_with_tax(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        inv = im.create_invoice("u11", "Taxed Client", line_items=[
            {"description": "Work", "quantity": 1, "unit_price": 1000},
        ], tax_rate=10)
        assert inv["total"] == 1100.0

    def test_invoice_with_discount(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        inv = im.create_invoice("u12", "Discounted", line_items=[
            {"description": "Work", "quantity": 1, "unit_price": 1000},
        ], discount=100)
        assert inv["total"] == 900.0

    def test_mark_paid(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        inv = im.create_invoice("u13", "Pay Me", line_items=[
            {"description": "Work", "quantity": 1, "unit_price": 500}])
        im.mark_sent(inv["id"])
        result = im.mark_paid(inv["id"], payment_method="Zelle")
        assert result["updated"]

    def test_create_proposal(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        prop = im.create_proposal("u14", "Big Proposal", "Client X",
            pricing_items=[
                {"description": "Phase 1", "amount": 5000},
                {"description": "Phase 2", "amount": 10000},
            ])
        assert prop["proposal_number"] == "PROP-0001"
        assert prop["total"] == 15000.0

    def test_revenue_dashboard(self):
        from core.invoicing import InvoiceManager
        im = InvoiceManager()
        dash = im.get_revenue_dashboard("u10")
        assert "total_invoiced" in dash
        assert "total_paid" in dash
        assert "outstanding" in dash


# ═══════════════════════════════════════════════════════════════
# TASK BOARD TESTS
# ═══════════════════════════════════════════════════════════════

class TestTasks:
    def test_create_project(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u1", "Test Project")
        assert p["id"].startswith("proj_")

    def test_create_project_from_template(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u20", "Launch", template="product_launch")
        assert p["tasks_created"] == 10

    def test_create_task(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u21", "Task Test")
        t = tm.create_task(p["id"], "u21", "Do something", priority="high")
        assert t["id"].startswith("task_")
        assert t["priority"] == "high"

    def test_move_task(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u22", "Move Test")
        t = tm.create_task(p["id"], "u22", "Movable")
        result = tm.move_task(t["id"], "in_progress")
        assert result["updated"]

    def test_complete_task(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u23", "Complete Test")
        t = tm.create_task(p["id"], "u23", "Finish me")
        result = tm.complete_task(t["id"])
        assert result["updated"]

    def test_subtasks(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u24", "Sub Test")
        t = tm.create_task(p["id"], "u24", "Parent Task")
        sub = tm.add_subtask(t["id"], "Subtask 1")
        assert sub["id"].startswith("sub_")
        result = tm.toggle_subtask(sub["id"])
        assert result["toggled"]

    def test_task_comments(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u25", "Comment Test")
        t = tm.create_task(p["id"], "u25", "Commentable")
        c = tm.add_comment(t["id"], "u25", "This is a comment")
        assert c["id"].startswith("cmt_")

    def test_kanban_board(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u26", "Board Test")
        tm.create_task(p["id"], "u26", "Task A", column="todo")
        tm.create_task(p["id"], "u26", "Task B", column="in_progress")
        board = tm.get_board(p["id"])
        assert "board" in board
        assert len(board["board"]) == 5  # Default columns

    def test_dashboard(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        dash = tm.get_dashboard("u26")
        assert "total_open" in dash
        assert "overdue" in dash

    def test_create_tasks_from_action_items(self):
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u27", "RT Tasks")
        items = [
            {"content": "Follow up with client", "author": "Strategy Bot", "tags": ["priority:high"]},
            {"content": "Draft proposal", "author": "Marketing Bot", "tags": ["priority:medium"]},
        ]
        created = tm.create_tasks_from_action_items(p["id"], "u27", items)
        assert len(created) == 2


# ═══════════════════════════════════════════════════════════════
# SOCIAL MEDIA TESTS
# ═══════════════════════════════════════════════════════════════

class TestSocialMedia:
    def test_platforms(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        platforms = sm.get_platforms()
        assert "twitter" in platforms
        assert "linkedin" in platforms
        assert len(platforms) == 7

    def test_create_campaign(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        c = sm.create_campaign("u30", "Test Campaign",
            platforms=["twitter", "linkedin"], objective="Brand awareness")
        assert c["id"].startswith("camp_")
        assert c["status"] == "draft"

    def test_create_post(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        c = sm.create_campaign("u31", "Post Test")
        p = sm.create_post(c["id"], "twitter", "Hello world! #test",
                           scheduled_at="2026-04-01T09:00:00")
        assert p["id"].startswith("post_")
        assert p["status"] == "scheduled"
        assert p["char_count"] == 18

    def test_char_limit_enforcement(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        c = sm.create_campaign("u32", "Limit Test")
        # Twitter limit is 280
        long_text = "x" * 281
        result = sm.create_post(c["id"], "twitter", long_text)
        assert "error" in result

    def test_bulk_schedule(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        c = sm.create_campaign("u33", "Bulk Test")
        result = sm.bulk_schedule(c["id"], [
            {"platform": "twitter", "content": "Post 1", "scheduled_at": "2026-04-01T09:00:00"},
            {"platform": "linkedin", "content": "Post 2", "scheduled_at": "2026-04-01T10:00:00"},
            {"platform": "twitter", "content": "Post 3", "scheduled_at": "2026-04-02T09:00:00"},
        ])
        assert result["created"] == 3
        assert result["errors"] == 0

    def test_calendar_view(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        c = sm.create_campaign("u35", "Calendar Test")
        sm.create_post(c["id"], "twitter", "Day 1", scheduled_at="2026-04-01T09:00:00")
        sm.create_post(c["id"], "twitter", "Day 2", scheduled_at="2026-04-02T09:00:00")
        cal = sm.get_calendar("u35", "2026-04-01", "2026-04-03")
        assert cal["total_posts"] == 2

    def test_campaign_analytics(self):
        from core.social_media import SocialMediaManager
        sm = SocialMediaManager()
        c = sm.create_campaign("u36", "Analytics Test")
        sm.create_post(c["id"], "twitter", "A")
        sm.create_post(c["id"], "linkedin", "B")
        analytics = sm.get_campaign_analytics(c["id"])
        assert analytics["total_posts"] == 2
        assert "twitter" in analytics["by_platform"]


# ═══════════════════════════════════════════════════════════════
# WHITEBOARD TESTS
# ═══════════════════════════════════════════════════════════════

class TestWhiteboard:
    def test_create_whiteboard(self):
        from core.whiteboard import RoundtableWhiteboard
        wb = RoundtableWhiteboard()
        w = wb.create("rt_test1", "u1")
        assert len(w["sections"]) == 4

    def test_add_note(self):
        from core.whiteboard import RoundtableWhiteboard
        wb = RoundtableWhiteboard()
        wb.create("rt_test2", "u1")
        note = wb.add_note("rt_test2", "ideas", "Great idea!", author="Bot")
        assert note["id"].startswith("note_")
        assert note["section_id"] == "ideas"

    def test_action_items(self):
        from core.whiteboard import RoundtableWhiteboard
        wb = RoundtableWhiteboard()
        wb.create("rt_test3", "u1")
        wb.add_action_item("rt_test3", "Follow up", assigned_to="Jeremy")
        items = wb.get_action_items("rt_test3")
        assert len(items) >= 1

    def test_export_markdown(self):
        from core.whiteboard import RoundtableWhiteboard
        wb = RoundtableWhiteboard()
        wb.create("rt_test4", "u1")
        wb.add_note("rt_test4", "decisions", "We decided X")
        md = wb.export_markdown("rt_test4")
        assert "Decisions" in md
        assert "We decided X" in md

    def test_add_custom_section(self):
        from core.whiteboard import RoundtableWhiteboard
        wb = RoundtableWhiteboard()
        wb.create("rt_test5", "u1")
        sec = wb.add_section("rt_test5", "Risks", color="#ef4444", icon="⚠️")
        assert sec["title"] == "Risks"


# ═══════════════════════════════════════════════════════════════
# GOALS / KPI TESTS
# ═══════════════════════════════════════════════════════════════

class TestGoals:
    def test_create_goal(self):
        from core.business_os import GoalTracker
        gt = GoalTracker()
        g = gt.create_goal("u40", "Hit $100K MRR", target_value=100000,
                           target_unit="USD", category="revenue")
        assert g["id"].startswith("goal_")

    def test_update_progress(self):
        from core.business_os import GoalTracker
        gt = GoalTracker()
        g = gt.create_goal("u41", "Close 20 deals", target_value=20)
        result = gt.update_progress(g["id"], 12, note="End of Q1")
        assert result["progress_pct"] == 60.0
        assert result["status"] == "on_track"

    def test_complete_goal(self):
        from core.business_os import GoalTracker
        gt = GoalTracker()
        g = gt.create_goal("u42", "Small goal", target_value=5)
        gt.update_progress(g["id"], 5)
        result = gt.complete_goal(g["id"])
        assert result["completed"]

    def test_key_results(self):
        from core.business_os import GoalTracker
        gt = GoalTracker()
        obj = gt.create_goal("u43", "Grow Revenue", target_value=100000)
        kr1 = gt.create_goal("u43", "Close 20 deals", target_value=20, parent_id=obj["id"])
        kr2 = gt.create_goal("u43", "Reduce churn to 3%", target_value=3, parent_id=obj["id"])
        full = gt.get_goal(obj["id"])
        assert len(full["key_results"]) == 2

    def test_goal_dashboard(self):
        from core.business_os import GoalTracker
        gt = GoalTracker()
        gt.create_goal("u44", "Dashboard Goal", target_value=10, category="business")
        dash = gt.get_dashboard("u44")
        assert "active_objectives" in dash
        assert dash["active_objectives"] >= 1


# ═══════════════════════════════════════════════════════════════
# EMAIL COMPOSER TESTS
# ═══════════════════════════════════════════════════════════════

class TestEmailComposer:
    def test_create_draft(self):
        from core.business_os import EmailComposer
        ec = EmailComposer()
        d = ec.create_draft("u50", "test@test.com", "Hello", "Body text")
        assert d["id"].startswith("email_")
        assert d["status"] == "draft"

    def test_list_outbox(self):
        from core.business_os import EmailComposer
        ec = EmailComposer()
        ec.create_draft("u51", "a@a.com", "Sub 1", "Body 1")
        ec.create_draft("u51", "b@b.com", "Sub 2", "Body 2")
        emails = ec.list_outbox("u51")
        assert len(emails) >= 2

    def test_delete_draft(self):
        from core.business_os import EmailComposer
        ec = EmailComposer()
        d = ec.create_draft("u52", "del@test.com", "Delete Me", "Body")
        ec.delete_draft(d["id"])
        assert ec.get_email(d["id"]) is None


# ═══════════════════════════════════════════════════════════════
# EXPENSE TRACKER TESTS
# ═══════════════════════════════════════════════════════════════

class TestExpenses:
    def test_add_expense(self):
        from core.business_os import ExpenseTracker
        et = ExpenseTracker()
        e = et.add_expense("u60", "AWS Hosting", 250, category="hosting", vendor="Amazon")
        assert e["id"].startswith("exp_")
        assert e["amount"] == 250

    def test_expense_summary(self):
        from core.business_os import ExpenseTracker
        et = ExpenseTracker()
        et.add_expense("u61", "Software", 100, category="software")
        et.add_expense("u61", "Travel", 500, category="travel")
        summary = et.get_summary("u61")
        assert summary["total_expenses"] == 600.0
        assert len(summary["by_category"]) >= 2

    def test_filter_by_category(self):
        from core.business_os import ExpenseTracker
        et = ExpenseTracker()
        et.add_expense("u62", "Item A", 50, category="software")
        et.add_expense("u62", "Item B", 75, category="hosting")
        filtered = et.list_expenses("u62", category="software")
        assert all(e["category"] == "software" for e in filtered)


# ═══════════════════════════════════════════════════════════════
# CRM CUSTOMIZATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestCRMCustomization:
    def test_create_custom_field(self):
        from core.crm_customization import CustomFieldManager
        cf = CustomFieldManager()
        f = cf.create_field("u70", "contact", "LinkedIn URL", field_type="url")
        assert f["field_key"] == "linkedin_url"
        assert f["field_type"] == "url"

    def test_field_validation(self):
        from core.crm_customization import CustomFieldManager
        cf = CustomFieldManager()
        assert cf.validate_value("email", "good@email.com")["valid"]
        assert not cf.validate_value("email", "bademail")["valid"]
        assert cf.validate_value("number", 42)["valid"]
        assert not cf.validate_value("number", "not_a_number")["valid"]
        assert cf.validate_value("rating", 3)["valid"]
        assert not cf.validate_value("rating", 6)["valid"]
        assert cf.validate_value("url", "https://test.com")["valid"]
        assert not cf.validate_value("url", "not-a-url")["valid"]
        assert cf.validate_value("select", "A", options=["A", "B"])["valid"]
        assert not cf.validate_value("select", "C", options=["A", "B"])["valid"]

    def test_create_pipeline(self):
        from core.crm_customization import PipelineManager
        pm = PipelineManager()
        p = pm.create_pipeline("u71", "Custom Pipeline", stages=[
            {"label": "Stage 1", "color": "#aaa", "type": "open"},
            {"label": "Stage 2", "color": "#bbb", "type": "won"},
        ])
        assert len(p["stages"]) == 2

    def test_saved_view(self):
        from core.crm_customization import SavedViewManager
        sv = SavedViewManager()
        v = sv.create_view("u72", "Hot Leads", "contact",
            filters={"tags": ["hot"]}, sort_by="created_at")
        assert v["name"] == "Hot Leads"
        views = sv.list_views("u72")
        assert len(views) >= 1

    def test_custom_activity_type(self):
        from core.crm_customization import ActivityTypeManager
        at = ActivityTypeManager()
        t = at.create_type("u73", "Site Visit", icon="🏢")
        assert t["id"] == "site_visit"
        types = at.get_types("u73")
        assert len(types) >= 6  # 5 defaults + 1 custom


# ═══════════════════════════════════════════════════════════════
# SETUP CONCIERGE TESTS
# ═══════════════════════════════════════════════════════════════

class TestSetupConcierge:
    def test_detect_crm_intent(self):
        from core.setup_concierge import detect_intent
        r = detect_intent("Help me set up my CRM")
        assert r["intent"] == "crm"

    def test_detect_social_intent(self):
        from core.setup_concierge import detect_intent
        r = detect_intent("create a social media campaign")
        assert r["intent"] == "social_media"

    def test_detect_invoicing_intent(self):
        from core.setup_concierge import detect_intent
        r = detect_intent("set up invoicing for my business")
        assert r["intent"] == "invoicing"

    def test_detect_no_intent(self):
        from core.setup_concierge import detect_intent
        r = detect_intent("tell me about dogs")
        assert r["intent"] is None

    def test_start_session(self):
        from core.setup_concierge import SetupConcierge
        sc = SetupConcierge()
        r = sc.start_session("u80", intent="crm")
        assert r["session_id"].startswith("setup_")
        assert r["intent"] == "crm"
        assert r["awaiting_input"]

    def test_full_crm_flow(self):
        from core.setup_concierge import SetupConcierge
        sc = SetupConcierge()
        r = sc.start_session("u81", intent="crm")
        sid = r["session_id"]
        r = sc.respond(sid, "u81", "SaaS")
        r = sc.respond(sid, "u81", "Sounds good")
        r = sc.respond(sid, "u81", "Website, LinkedIn")
        r = sc.respond(sid, "u81", "Start fresh")
        assert r["complete"]
        assert r["summary"]["pipeline_stages"] == 6

    def test_intent_from_message(self):
        from core.setup_concierge import SetupConcierge
        sc = SetupConcierge()
        r = sc.start_session("u82", user_message="I need to track expenses")
        assert r["intent"] == "expenses"


# ═══════════════════════════════════════════════════════════════
# EDUCATION THEME TESTS
# ═══════════════════════════════════════════════════════════════

class TestEducationTheme:
    def test_age_group_detection(self):
        from core.edu_theme import EducationThemeEngine
        eng = EducationThemeEngine()
        assert eng.get_age_group(6) == "early_elementary"
        assert eng.get_age_group(9) == "upper_elementary"
        assert eng.get_age_group(12) == "middle_school"
        assert eng.get_age_group(16) == "high_school"

    def test_theme_colors_change_with_age(self):
        from core.edu_theme import EducationThemeEngine
        eng = EducationThemeEngine()
        young = eng.get_theme(age=6)
        old = eng.get_theme(age=16)
        assert young["colors"]["primary"] != old["colors"]["primary"]
        assert young["colors"]["background"] != old["colors"]["background"]

    def test_vocabulary_changes_with_age(self):
        from core.edu_theme import EducationThemeEngine
        eng = EducationThemeEngine()
        young = eng.get_theme(age=6)
        old = eng.get_theme(age=16)
        assert young["vocabulary"]["space"] == "Helper"
        assert old["vocabulary"]["space"] == "Space"
        assert young["vocabulary"]["send_message"] == "Ask!"
        assert old["vocabulary"]["send_message"] == "Send"

    def test_css_generation(self):
        from core.edu_theme import EducationThemeEngine
        eng = EducationThemeEngine()
        css = eng.get_css_variables(age=6)
        assert "--edu-primary" in css
        assert "#4CC9F0" in css  # early elementary primary

    def test_all_themes_available(self):
        from core.edu_theme import EducationThemeEngine
        eng = EducationThemeEngine()
        themes = eng.get_all_themes()
        assert len(themes) == 4


# ═══════════════════════════════════════════════════════════════
# EDUCATION I18N TESTS
# ═══════════════════════════════════════════════════════════════

class TestEducationI18n:
    def test_english_translation(self):
        from core.edu_i18n import EducationI18n
        ei = EducationI18n()
        t = ei.get_translation("en", "early_elementary")
        assert t["ui"]["space"] == "Helper"
        assert "greeting" in t["ai"]

    def test_spanish_translation(self):
        from core.edu_i18n import EducationI18n
        ei = EducationI18n()
        t = ei.get_translation("es", "early_elementary")
        assert t["ui"]["space"] == "Ayudante"

    def test_japanese_translation(self):
        from core.edu_i18n import EducationI18n
        ei = EducationI18n()
        t = ei.get_translation("ja", "early_elementary")
        assert "おてつだい" in t["ui"]["space"]

    def test_arabic_rtl(self):
        from core.edu_i18n import EducationI18n
        ei = EducationI18n()
        langs = ei.get_supported_languages()
        ar = [l for l in langs if l["code"] == "ar"][0]
        assert ar["rtl"] is True

    def test_all_languages_all_ages(self):
        from core.edu_i18n import EducationI18n
        ei = EducationI18n()
        langs = ["en", "es", "fr", "pt", "zh", "ja", "ar"]
        groups = ["early_elementary", "upper_elementary", "middle_school", "high_school"]
        for lang in langs:
            for group in groups:
                t = ei.get_translation(lang, group)
                assert "ui" in t
                assert "ai" in t
                assert "subjects" in t


# ═══════════════════════════════════════════════════════════════
# BIZ UPGRADES TESTS
# ═══════════════════════════════════════════════════════════════

class TestBizUpgrades:
    def test_partial_payment(self):
        from core.invoicing import InvoiceManager
        from core.biz_upgrades import PaymentTracker
        im = InvoiceManager()
        inv = im.create_invoice("u90", "Partial Test", line_items=[
            {"description": "Work", "quantity": 1, "unit_price": 1000}])
        pt = PaymentTracker()
        r = pt.record_payment(inv["id"], 400, method="Check")
        assert r["total_paid"] == 400
        assert r["balance"] == 600
        assert not r["fully_paid"]
        r2 = pt.record_payment(inv["id"], 600, method="Wire")
        assert r2["balance"] == 0
        assert r2["fully_paid"]

    def test_time_tracking(self):
        from core.biz_upgrades import TaskTimeTracker
        from core.tasks import TaskManager
        tm = TaskManager()
        p = tm.create_project("u91", "Time Test")
        t = tm.create_task(p["id"], "u91", "Timed Task")
        tt = TaskTimeTracker()
        # Manual log
        r = tt.log_manual(t["id"], "u91", 90, note="Morning work")
        assert r["minutes"] == 90
        task_time = tt.get_task_time(t["id"])
        assert task_time["total_minutes"] == 90
        assert task_time["total_hours"] == 1.5

    def test_email_templates(self):
        from core.biz_upgrades import EmailTemplateManager
        etm = EmailTemplateManager()
        t = etm.create_template("u92", "Follow Up", "Re: Our Conversation",
            "Hi, following up...", category="sales")
        assert t["name"] == "Follow Up"
        templates = etm.list_templates("u92")
        assert len(templates) >= 1

    def test_email_signature(self):
        from core.biz_upgrades import EmailTemplateManager
        etm = EmailTemplateManager()
        etm.set_signature("u93", "<p>Best, Jeremy</p>")
        sig = etm.get_signature("u93")
        assert "Jeremy" in sig

    def test_custom_expense_categories(self):
        from core.biz_upgrades import CustomExpenseCategoryManager
        cem = CustomExpenseCategoryManager()
        c = cem.create_category("u94", "Client Gifts", icon="🎁", tax_deductible=True)
        assert c["name"] == "Client Gifts"
        cats = cem.list_categories("u94")
        assert any(c["name"] == "Client Gifts" for c in cats)

    def test_hashtag_groups(self):
        from core.biz_upgrades import HashtagManager
        hm = HashtagManager()
        g = hm.create_group("u95", "AI Tags", ["#AI", "#MachineLearning", "#Tech"])
        assert g["count"] == 3
        groups = hm.list_groups("u95")
        assert len(groups) >= 1


# ═══════════════════════════════════════════════════════════════
# LAUNCH FIXES TESTS
# ═══════════════════════════════════════════════════════════════

class TestLaunchFixes:
    def test_plan_change_preview(self):
        from core.launch_fixes import PlanChangeManager
        pc = PlanChangeManager()
        preview = pc.preview_change("starter", "pro")
        assert preview["is_upgrade"]
        assert preview["price_change"]["from"] == 7
        assert preview["price_change"]["to"] == 29
        assert len(preview["features_gained"]) > 0

    def test_plan_downgrade_preview(self):
        from core.launch_fixes import PlanChangeManager
        pc = PlanChangeManager()
        preview = pc.preview_change("business", "pro")
        assert not preview["is_upgrade"]
        assert preview["direction"] == "downgrade"

    def test_conversation_folders(self):
        from core.launch_fixes import ConversationOrganizer
        co = ConversationOrganizer()
        f = co.create_folder("u100", "Clients", color="#3b82f6")
        assert f["name"] == "Clients"
        folders = co.list_folders("u100")
        assert len(folders) >= 1

    def test_spend_alerts(self):
        from core.launch_fixes import SpendAlertManager
        sa = SpendAlertManager()
        sa.set_budget("u101", 100, alert_at_pct=80)
        # Under budget
        check = sa.check_budget("u101", 50)
        assert check["alert"] is None
        # Warning
        check = sa.check_budget("u101", 85)
        assert check["alert"]["level"] == "warning"
        # Exceeded
        check = sa.check_budget("u101", 110)
        assert check["alert"]["level"] == "exceeded"

    def test_cancellation_reasons(self):
        from core.launch_fixes import CancellationManager
        cm = CancellationManager()
        assert len(cm.CANCEL_REASONS) >= 7
        assert "too_expensive" in cm.CANCEL_REASONS


# ═══════════════════════════════════════════════════════════════
# DOCUMENT EXPORT TESTS
# ═══════════════════════════════════════════════════════════════

class TestDocumentExport:
    def test_conversation_to_markdown(self):
        from core.document_export import DocumentExporter
        de = DocumentExporter()
        md = de.conversation_to_markdown(
            {"title": "Test", "agent_name": "Bot", "created_at": "2026-01-01"},
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}])
        assert "Test" in md
        assert "Hello" in md
        assert "Hi!" in md

    def test_conversation_to_csv(self):
        from core.document_export import DocumentExporter
        de = DocumentExporter()
        csv = de.conversation_to_csv([
            {"created_at": "2026-01-01", "role": "user", "content": "Test",
             "model": "claude", "tokens_used": 50}])
        assert "Test" in csv
        assert "user" in csv

    def test_generic_xlsx(self):
        from core.document_export import DocumentExporter
        de = DocumentExporter()
        data = de.data_to_xlsx(["Name", "Value"], [["A", "1"], ["B", "2"]])
        assert len(data) > 0  # Valid bytes


# ═══════════════════════════════════════════════════════════════
# COMPETITIVE INTELLIGENCE TESTS
# ═══════════════════════════════════════════════════════════════

class TestCompetitiveIntel:
    def test_add_competitor(self):
        from core.business_tools import CompetitiveIntel
        ci = CompetitiveIntel()
        c = ci.add_competitor("u110", "Rival Inc", website="rival.com")
        assert c["name"] == "Rival Inc"

    def test_log_intel(self):
        from core.business_tools import CompetitiveIntel
        ci = CompetitiveIntel()
        c = ci.add_competitor("u111", "Competitor X")
        i = ci.log_intel(c["id"], "product_launch", "They launched a new feature")
        assert i["type"] == "product_launch"

    def test_analysis_prompt(self):
        from core.business_tools import CompetitiveIntel
        ci = CompetitiveIntel()
        ci.add_competitor("u112", "BigCo", description="Enterprise player")
        prompt = ci.build_analysis_prompt("u112")
        assert "BigCo" in prompt
        assert "COMPETITIVE POSITIONING" in prompt


# ═══════════════════════════════════════════════════════════════
# CLIENT PORTAL TESTS
# ═══════════════════════════════════════════════════════════════

class TestClientPortal:
    def test_create_share(self):
        from core.business_tools import ClientPortal
        cp = ClientPortal()
        s = cp.create_share("u120", "Project Report", "conversation", "conv_123",
                            client_name="Client X", expires_days=7)
        assert s["token"]
        assert "/portal/" in s["share_url"]

    def test_access_share(self):
        from core.business_tools import ClientPortal
        cp = ClientPortal()
        s = cp.create_share("u121", "Deliverable", "roundtable", "rt_456")
        result = cp.get_share(s["token"])
        assert result["title"] == "Deliverable"
        assert result["view_count"] == 1

    def test_password_protected_share(self):
        from core.business_tools import ClientPortal
        cp = ClientPortal()
        s = cp.create_share("u122", "Secret Doc", "invoice", "inv_789", password="mypass")
        # Without password
        result = cp.get_share(s["token"])
        assert result.get("error") == "password_required"
        # With wrong password
        result = cp.get_share(s["token"], password="wrong")
        assert "Incorrect" in result.get("error", "")
        # With correct password
        result = cp.get_share(s["token"], password="mypass")
        assert result["title"] == "Secret Doc"

    def test_revoke_share(self):
        from core.business_tools import ClientPortal
        cp = ClientPortal()
        s = cp.create_share("u123", "Revokable", "doc", "doc_1")
        cp.revoke_share(s["id"])
        result = cp.get_share(s["token"])
        assert "not found" in result.get("error", "").lower() or "expired" in result.get("error", "").lower()


# ═══════════════════════════════════════════════════════════════
# CONTRACT TEMPLATES TESTS
# ═══════════════════════════════════════════════════════════════

class TestContracts:
    def test_list_templates(self):
        from core.business_tools import ContractTemplateManager
        ct = ContractTemplateManager()
        templates = ct.get_templates()
        assert "nda" in templates
        assert "freelancer_agreement" in templates
        assert "sow" in templates
        assert "consulting_agreement" in templates

    def test_build_prompt(self):
        from core.business_tools import ContractTemplateManager
        ct = ContractTemplateManager()
        result = ct.build_prompt("nda", {
            "party_1_name": "Acme Corp", "party_1_address": "123 Main St",
            "party_2_name": "Vendor LLC", "party_2_address": "456 Oak Ave",
            "effective_date": "2026-03-10", "duration_months": "12",
            "governing_state": "Nevada", "nda_type": "Mutual",
        })
        assert "Acme Corp" in result["prompt"]
        assert result["disclaimer"]


# ═══════════════════════════════════════════════════════════════
# HR ASSISTANT TESTS
# ═══════════════════════════════════════════════════════════════

class TestHRAssistant:
    def test_job_description_prompt(self):
        from core.business_tools import HRAssistant
        hr = HRAssistant()
        result = hr.build_job_description_prompt("Software Engineer",
            department="Engineering", location="Remote")
        assert "Software Engineer" in result["prompt"]
        assert "Remote" in result["prompt"]

    def test_interview_prompt(self):
        from core.business_tools import HRAssistant
        hr = HRAssistant()
        result = hr.build_interview_prompt("Product Manager", stage="final_round")
        assert "Product Manager" in result["prompt"]
        assert "BEHAVIORAL" in result["prompt"]

    def test_onboarding_templates(self):
        from core.business_tools import HRAssistant
        hr = HRAssistant()
        templates = hr.get_onboarding_templates()
        assert "general" in templates
        assert "remote" in templates
        checklist = hr.get_onboarding_checklist("general")
        assert checklist["total_items"] >= 10
