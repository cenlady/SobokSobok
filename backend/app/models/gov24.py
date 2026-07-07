from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, func

from app.core.database import Base


class Gov24ServiceList(Base):
    __tablename__ = "gov24_service_lists"

    service_id = Column(String(50), primary_key=True, index=True)
    registration_datetime = Column(String(30), nullable=True)
    department_name = Column(String(300), nullable=True)
    user_type = Column(String(500), nullable=True, index=True)
    detail_url = Column(String(1000), nullable=True)
    service_name = Column(String(500), nullable=False, index=True)
    service_purpose_summary = Column(Text, nullable=True)
    service_field = Column(String(200), nullable=True, index=True)
    selection_criteria = Column(Text, nullable=True)
    organization_name = Column(String(300), nullable=True, index=True)
    organization_type = Column(String(100), nullable=True, index=True)
    organization_code = Column(String(50), nullable=True, index=True)
    modified_datetime = Column(String(30), nullable=True, index=True)
    application_deadline = Column(Text, nullable=True)
    application_method = Column(Text, nullable=True)
    contact_phone = Column(Text, nullable=True)
    reception_institution = Column(Text, nullable=True)
    view_count = Column(Integer, nullable=True)
    support_content = Column(Text, nullable=True)
    support_target = Column(Text, nullable=True)
    support_type = Column(String(500), nullable=True, index=True)
    raw_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)


class Gov24ServiceDetail(Base):
    __tablename__ = "gov24_service_details"

    service_id = Column(String(50), primary_key=True, index=True)
    required_docs_by_official = Column(Text, nullable=True)
    required_docs = Column(Text, nullable=True)
    contact = Column(Text, nullable=True)
    laws = Column(Text, nullable=True)
    identity_required_docs = Column(Text, nullable=True)
    service_name = Column(String(500), nullable=False, index=True)
    service_purpose = Column(Text, nullable=True)
    selection_criteria = Column(Text, nullable=True)
    organization_name = Column(String(300), nullable=True, index=True)
    modified_date = Column(String(30), nullable=True, index=True)
    application_deadline = Column(Text, nullable=True)
    application_method = Column(Text, nullable=True)
    online_application_url = Column(String(1000), nullable=True)
    local_laws = Column(Text, nullable=True)
    reception_institution_name = Column(Text, nullable=True)
    support_content = Column(Text, nullable=True)
    support_target = Column(Text, nullable=True)
    support_type = Column(String(500), nullable=True, index=True)
    administrative_rules = Column(Text, nullable=True)
    raw_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)


class Gov24SupportCondition(Base):
    __tablename__ = "gov24_support_conditions"

    service_id = Column(String(50), primary_key=True, index=True)
    service_name = Column(String(500), nullable=False, index=True)
    ja0101_male = Column(String(30), nullable=True)
    ja0102_female = Column(String(30), nullable=True)
    ja0110_age_start = Column(String(30), nullable=True)
    ja0111_age_end = Column(String(30), nullable=True)
    ja0201_income_0_50 = Column(String(30), nullable=True)
    ja0202_income_51_75 = Column(String(30), nullable=True)
    ja0203_income_76_100 = Column(String(30), nullable=True)
    ja0204_income_101_200 = Column(String(30), nullable=True)
    ja0205_income_over_200 = Column(String(30), nullable=True)
    ja0301_pre_parent_infertility = Column(String(30), nullable=True)
    ja0302_pregnant = Column(String(30), nullable=True)
    ja0303_childbirth_adoption = Column(String(30), nullable=True)
    ja0313_farmer = Column(String(30), nullable=True)
    ja0314_fisher = Column(String(30), nullable=True)
    ja0315_livestock_farmer = Column(String(30), nullable=True)
    ja0316_forester = Column(String(30), nullable=True)
    ja0317_elementary_student = Column(String(30), nullable=True)
    ja0318_middle_school_student = Column(String(30), nullable=True)
    ja0319_high_school_student = Column(String(30), nullable=True)
    ja0320_college_student = Column(String(30), nullable=True)
    ja0322_no_personal_trait = Column(String(30), nullable=True)
    ja0326_worker = Column(String(30), nullable=True)
    ja0327_job_seeker = Column(String(30), nullable=True)
    ja0328_disabled = Column(String(30), nullable=True)
    ja0329_veteran = Column(String(30), nullable=True)
    ja0330_disease_patient = Column(String(30), nullable=True)
    ja0401_multicultural_family = Column(String(30), nullable=True)
    ja0402_north_korean_defector = Column(String(30), nullable=True)
    ja0403_single_parent_grandparent_family = Column(String(30), nullable=True)
    ja0404_single_person_household = Column(String(30), nullable=True)
    ja0410_no_household_trait = Column(String(30), nullable=True)
    ja0411_multi_child_family = Column(String(30), nullable=True)
    ja0412_homeless_household = Column(String(30), nullable=True)
    ja0413_new_resident = Column(String(30), nullable=True)
    ja0414_extended_family = Column(String(30), nullable=True)
    ja1101_pre_founder = Column(String(30), nullable=True)
    ja1102_operating_business = Column(String(30), nullable=True)
    ja1103_closing_business = Column(String(30), nullable=True)
    ja1201_restaurant_business = Column(String(30), nullable=True)
    ja1202_manufacturing_business = Column(String(30), nullable=True)
    ja1299_other_business = Column(String(30), nullable=True)
    ja2101_small_medium_business = Column(String(30), nullable=True)
    ja2102_social_welfare_facility = Column(String(30), nullable=True)
    ja2103_institution_group = Column(String(30), nullable=True)
    ja2201_company_manufacturing = Column(String(30), nullable=True)
    ja2202_company_agriculture_fishery_forestry = Column(String(30), nullable=True)
    ja2203_company_information_communication = Column(String(30), nullable=True)
    ja2299_company_other_business = Column(String(30), nullable=True)
    raw_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
