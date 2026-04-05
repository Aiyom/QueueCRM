"""Seed development data: super admin + sample tenant + services + staff."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(".env")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.core.security import hash_password
from app.models.tenant import Tenant, BusinessType
from app.models.tenant_subscription import TenantSubscription, SubscriptionStatus, SubscriptionPlan
from app.models.staff_user import StaffUser, StaffRole
from app.models.super_admin import SuperAdmin
from app.models.service import Service
from app.models.plan_config import PlanConfig
import app.models  # noqa: F401 — ensure all models registered


async def seed() -> None:
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # --- Check if already seeded ---
        existing = await db.scalar(select(SuperAdmin).limit(1))
        if existing:
            print("✅ Already seeded, skipping.")
            await engine.dispose()
            return

        # --- Super Admin ---
        super_admin = SuperAdmin(
            id=uuid.uuid4(),
            email="admin@queuecrm.sa",
            hashed_password=hash_password("Admin@1234"),
            full_name="Super Admin",
        )
        db.add(super_admin)
        print("✓ SuperAdmin: admin@queuecrm.sa / Admin@1234")

        # --- Demo Tenant (Auto Service) ---
        tenant_auto = Tenant(
            id=uuid.uuid4(),
            name="Al-Noor Auto Service",
            slug="al-noor-auto",
            business_type=BusinessType.auto_service,
            phone="+966501234567",
            d360_api_key=None,
            d360_channel_id=None,
        )
        db.add(tenant_auto)

        sub_auto = TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant_auto.id,
            plan=SubscriptionPlan.starter,
            status=SubscriptionStatus.trial,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(sub_auto)

        # Auto service staff
        admin_auto = StaffUser(
            id=uuid.uuid4(),
            tenant_id=tenant_auto.id,
            email="manager@alnoor.sa",
            hashed_password=hash_password("Manager@1234"),
            full_name="Ahmed Al-Noor",
            role=StaffRole.admin,
        )
        operator_auto = StaffUser(
            id=uuid.uuid4(),
            tenant_id=tenant_auto.id,
            email="operator@alnoor.sa",
            hashed_password=hash_password("Operator@1234"),
            full_name="Mohammed Ali",
            role=StaffRole.operator,
        )
        db.add_all([admin_auto, operator_auto])

        # Auto services
        auto_services = [
            ("تغيير زيت", "Oil Change", 20, 0),
            ("فحص شامل", "Full Inspection", 45, 1),
            ("غسيل سيارة", "Car Wash", 15, 2),
            ("تغيير إطارات", "Tire Change", 30, 3),
            ("شحن بطارية", "Battery Service", 20, 4),
        ]
        for name_ar, name_en, duration, order in auto_services:
            db.add(Service(
                id=uuid.uuid4(),
                tenant_id=tenant_auto.id,
                name_ar=name_ar,
                name_en=name_en,
                avg_duration_minutes=duration,
                sort_order=order,
            ))

        print(f"✓ Tenant: Al-Noor Auto Service (slug: al-noor-auto)")
        print(f"  Staff: manager@alnoor.sa / Manager@1234 (admin)")
        print(f"  Staff: operator@alnoor.sa / Operator@1234 (operator)")
        print(f"  Services: {len(auto_services)} services")

        # --- Demo Tenant (Barbershop) ---
        tenant_barber = Tenant(
            id=uuid.uuid4(),
            name="Khalid Barbershop",
            slug="khalid-barber",
            business_type=BusinessType.barbershop,
            phone="+966507654321",
        )
        db.add(tenant_barber)

        sub_barber = TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant_barber.id,
            plan=SubscriptionPlan.starter,
            status=SubscriptionStatus.trial,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(sub_barber)

        admin_barber = StaffUser(
            id=uuid.uuid4(),
            tenant_id=tenant_barber.id,
            email="admin@khalid-barber.sa",
            hashed_password=hash_password("Admin@1234"),
            full_name="Khalid Ibrahim",
            role=StaffRole.admin,
        )
        db.add(admin_barber)

        barber_services = [
            ("حلاقة شعر", "Haircut", 20, 0),
            ("حلاقة لحية", "Beard Trim", 15, 1),
            ("حلاقة + لحية", "Haircut + Beard", 30, 2),
            ("تنظيف البشرة", "Skin Care", 25, 3),
        ]
        for name_ar, name_en, duration, order in barber_services:
            db.add(Service(
                id=uuid.uuid4(),
                tenant_id=tenant_barber.id,
                name_ar=name_ar,
                name_en=name_en,
                avg_duration_minutes=duration,
                sort_order=order,
            ))

        print(f"✓ Tenant: Khalid Barbershop (slug: khalid-barber)")
        print(f"  Staff: admin@khalid-barber.sa / Admin@1234 (admin)")

        # --- Default plan catalog ---
        default_plans = [
            PlanConfig(
                id=uuid.uuid4(), slug="starter", sort_order=0,
                name_en="Starter", name_ar="ستارتر", name_ru="Стартер",
                price_usd=50,
                features=[
                    "Single queue",
                    "WhatsApp notifications",
                    "Basic dashboard",
                    "Email support",
                ],
            ),
            PlanConfig(
                id=uuid.uuid4(), slug="pro", sort_order=1,
                name_en="Pro", name_ar="برو", name_ru="Про",
                price_usd=150,
                features=[
                    "Unlimited queues",
                    "Full CRM",
                    "VIP priority",
                    "Advanced analytics",
                    "Priority support",
                ],
            ),
            PlanConfig(
                id=uuid.uuid4(), slug="business", sort_order=2,
                name_en="Business", name_ar="بيزنس", name_ru="Бизнес",
                price_usd=300,
                features=[
                    "Multiple branches",
                    "Advanced reports",
                    "Custom integration",
                    "Account manager",
                    "SLA guarantee",
                ],
            ),
        ]
        db.add_all(default_plans)
        print(f"✓ Plans: starter ($50), pro ($150), business ($300)")

        await db.commit()
        print("\n✅ Seed complete!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
