-- Supabase uses PostgreSQL tables, not MySQL databases or document collections.
-- Run this entire file in Supabase Dashboard > SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    full_name text not null default '',
    program text not null default '',
    study_year text not null default '',
    role text not null default 'student' check (role in ('student', 'admin')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.user_settings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    theme text not null default 'system' check (theme in ('light', 'dark', 'system')),
    language text not null default 'en',
    chat_preferences jsonb not null default '{}'::jsonb,
    notifications_enabled boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.career_paths (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    name text not null unique,
    description text not null,
    suggested_courses text[] not null default '{}',
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.skills (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null unique
);

create table if not exists public.career_path_skills (
    career_path_id uuid not null references public.career_paths(id) on delete cascade,
    skill_id uuid not null references public.skills(id) on delete cascade,
    is_core boolean not null default true,
    primary key (career_path_id, skill_id)
);

create table if not exists public.questionnaire_options (
    id uuid primary key default gen_random_uuid(),
    category text not null check (
        category in ('interests', 'skills', 'work_styles', 'subjects',
                     'goals', 'activities', 'priorities')
    ),
    code text not null,
    label text not null,
    is_active boolean not null default true,
    unique (category, code)
);

create table if not exists public.recommendation_rules (
    id uuid primary key default gen_random_uuid(),
    career_path_id uuid not null references public.career_paths(id) on delete cascade,
    option_id uuid not null references public.questionnaire_options(id) on delete cascade,
    points numeric(6,2) not null check (points >= 0),
    reason text not null default '',
    is_active boolean not null default true,
    unique (career_path_id, option_id)
);

create table if not exists public.questionnaire_submissions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    answers jsonb not null,
    recommendation_summary jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

alter table public.questionnaire_submissions
add column if not exists recommendation_summary jsonb not null default '[]'::jsonb;

create table if not exists public.submission_answers (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null references public.questionnaire_submissions(id) on delete cascade,
    category text not null,
    option_code text not null,
    unique (submission_id, category, option_code)
);

create table if not exists public.recommendation_results (
    id uuid primary key default gen_random_uuid(),
    submission_id uuid not null references public.questionnaire_submissions(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    career_path_id uuid not null references public.career_paths(id),
    rank_position smallint not null check (rank_position between 1 and 3),
    score numeric(6,2) not null,
    match_percentage smallint not null check (match_percentage between 0 and 100),
    match_tier text not null check (match_tier in ('Perfect', 'Great', 'Good', 'Exploratory')),
    explanation jsonb not null default '{}'::jsonb,
    coach_tip text not null default '',
    created_at timestamptz not null default now(),
    unique (submission_id, rank_position)
);

create table if not exists public.chat_conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text,
    status text not null default 'active' check (status in ('active', 'archived')),
    model text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    archived_at timestamptz
);

create table if not exists public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references public.chat_conversations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    status text not null default 'completed' check (status in ('pending', 'completed', 'failed')),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_user_settings_user_id on public.user_settings(user_id);
create index if not exists idx_questionnaire_submissions_user_id on public.questionnaire_submissions(user_id);
create index if not exists idx_questionnaire_submissions_user_created_at on public.questionnaire_submissions(user_id, created_at desc);
create index if not exists idx_recommendation_results_user_id_created_at on public.recommendation_results(user_id, created_at desc);
create index if not exists idx_chat_conversations_user_id_updated_at on public.chat_conversations(user_id, updated_at desc);
create index if not exists idx_chat_messages_conversation_created_at on public.chat_messages(conversation_id, created_at);
create index if not exists idx_chat_messages_user_id on public.chat_messages(user_id);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
    insert into public.profiles (id, email, full_name)
    values (
        new.id,
        coalesce(new.email, ''),
        coalesce(new.raw_user_meta_data ->> 'full_name', '')
    );
    insert into public.user_settings (user_id)
    values (new.id)
    on conflict (user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.user_settings enable row level security;
alter table public.career_paths enable row level security;
alter table public.skills enable row level security;
alter table public.career_path_skills enable row level security;
alter table public.questionnaire_options enable row level security;
alter table public.recommendation_rules enable row level security;
alter table public.questionnaire_submissions enable row level security;
alter table public.submission_answers enable row level security;
alter table public.recommendation_results enable row level security;
alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists "Public can read active careers" on public.career_paths;
create policy "Public can read active careers"
on public.career_paths for select
using (is_active = true);

drop policy if exists "Public can read skills" on public.skills;
create policy "Public can read skills"
on public.skills for select using (true);

drop policy if exists "Public can read career skills" on public.career_path_skills;
create policy "Public can read career skills"
on public.career_path_skills for select using (true);

drop policy if exists "Public can read active questionnaire options" on public.questionnaire_options;
create policy "Public can read active questionnaire options"
on public.questionnaire_options for select
using (is_active = true);

drop policy if exists "Public can read active recommendation rules" on public.recommendation_rules;
create policy "Public can read active recommendation rules"
on public.recommendation_rules for select
using (is_active = true);

drop policy if exists "Users can read their own profile" on public.profiles;
create policy "Users can read their own profile"
on public.profiles for select
using ((select auth.uid()) = id);

drop policy if exists "Users can update their own profile" on public.profiles;
create policy "Users can update their own profile"
on public.profiles for update
using ((select auth.uid()) = id)
with check ((select auth.uid()) = id);

drop policy if exists "Users can read their own settings" on public.user_settings;
create policy "Users can read their own settings"
on public.user_settings for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert their own settings" on public.user_settings;
create policy "Users can insert their own settings"
on public.user_settings for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own settings" on public.user_settings;
create policy "Users can update their own settings"
on public.user_settings for update
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can insert their own submissions" on public.questionnaire_submissions;
create policy "Users can insert their own submissions"
on public.questionnaire_submissions for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read their own submissions" on public.questionnaire_submissions;
create policy "Users can read their own submissions"
on public.questionnaire_submissions for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their old submissions" on public.questionnaire_submissions;
create policy "Users can delete their old submissions"
on public.questionnaire_submissions for delete
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert answers for their submissions" on public.submission_answers;
create policy "Users can insert answers for their submissions"
on public.submission_answers for insert
with check (
    exists (
        select 1 from public.questionnaire_submissions submission
        where submission.id = submission_id
          and submission.user_id = (select auth.uid())
    )
);

drop policy if exists "Users can read answers for their submissions" on public.submission_answers;
create policy "Users can read answers for their submissions"
on public.submission_answers for select
using (
    exists (
        select 1 from public.questionnaire_submissions submission
        where submission.id = submission_id
          and submission.user_id = (select auth.uid())
    )
);

drop policy if exists "Users can delete answers for their submissions" on public.submission_answers;
create policy "Users can delete answers for their submissions"
on public.submission_answers for delete
using (
    exists (
        select 1 from public.questionnaire_submissions submission
        where submission.id = submission_id
          and submission.user_id = (select auth.uid())
    )
);

drop policy if exists "Users can insert their own recommendation results" on public.recommendation_results;
create policy "Users can insert their own recommendation results"
on public.recommendation_results for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read their own recommendation results" on public.recommendation_results;
create policy "Users can read their own recommendation results"
on public.recommendation_results for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own recommendation results" on public.recommendation_results;
create policy "Users can delete their own recommendation results"
on public.recommendation_results for delete
using ((select auth.uid()) = user_id);

drop policy if exists "Users can manage their own chat conversations" on public.chat_conversations;
create policy "Users can manage their own chat conversations"
on public.chat_conversations for all
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read messages from their conversations" on public.chat_messages;
create policy "Users can read messages from their conversations"
on public.chat_messages for select
using (
    exists (
        select 1 from public.chat_conversations conversation
        where conversation.id = conversation_id
          and conversation.user_id = (select auth.uid())
    )
);

drop policy if exists "Users can insert messages into their conversations" on public.chat_messages;
create policy "Users can insert messages into their conversations"
on public.chat_messages for insert
with check (
    (select auth.uid()) = user_id
    and exists (
        select 1 from public.chat_conversations conversation
        where conversation.id = conversation_id
          and conversation.user_id = (select auth.uid())
    )
);

drop policy if exists "Users can update messages in their conversations" on public.chat_messages;
create policy "Users can update messages in their conversations"
on public.chat_messages for update
using (
    exists (
        select 1 from public.chat_conversations conversation
        where conversation.id = conversation_id
          and conversation.user_id = (select auth.uid())
    )
)
with check (
    (select auth.uid()) = user_id
    and exists (
        select 1 from public.chat_conversations conversation
        where conversation.id = conversation_id
          and conversation.user_id = (select auth.uid())
    )
);

insert into public.career_paths (slug, name, description, suggested_courses)
values
('software', 'Software Engineer', 'Designs, builds, tests, and maintains reliable software systems.', array['Software Engineering','Git and GitHub','Data Structures and Algorithms']),
('web', 'Full Stack Developer', 'Builds complete web products across user interfaces, servers, APIs, and databases.', array['Responsive Web Design','JavaScript','Flask or Django','Database Fundamentals']),
('mobile', 'Mobile App Developer', 'Builds applications and experiences for Android, iOS, and cross-platform devices.', array['Android Development','Flutter','React Native','Mobile UI Design']),
('data', 'Data Analyst', 'Transforms raw data into trustworthy reports and practical business insights.', array['SQL','Excel','Python for Data Analysis','Power BI or Tableau']),
('security', 'Cybersecurity Analyst', 'Finds vulnerabilities, monitors threats, and protects systems and information.', array['CompTIA Security+','Ethical Hacking','Network Security','Linux Fundamentals']),
('networking', 'Network Engineer', 'Installs, operates, secures, and troubleshoots networks and infrastructure.', array['CompTIA Network+','Cisco CCNA','Linux Administration','Cloud Fundamentals']),
('design', 'UI/UX Designer', 'Studies user needs and designs useful, accessible, and appealing experiences.', array['Figma','UX Research','Interaction Design','Web Accessibility']),
('database', 'Database Administrator', 'Maintains secure, reliable, organized, and efficient database systems.', array['MySQL Administration','Advanced SQL','Database Design','Cloud Databases']),
('ai', 'AI/ML Engineer', 'Builds and evaluates systems that learn from data to predict or automate tasks.', array['Python','Machine Learning','Linear Algebra','Deep Learning']),
('data_scientist', 'Data Scientist', 'Uses statistics, programming, and experimentation to discover patterns and build predictive insights.', array['Python for Data Science','Applied Statistics','Machine Learning','Data Storytelling']),
('cloud', 'Cloud Engineer', 'Designs, deploys, secures, and maintains scalable services on cloud platforms.', array['AWS Cloud Practitioner','Azure Fundamentals','Linux Administration','Cloud Security']),
('business_analyst', 'Business Analyst', 'Connects business needs with technology solutions through analysis, communication, and process design.', array['Business Analysis Fundamentals','Requirements Engineering','SQL','Data Visualization']),
('game', 'Game Developer', 'Creates interactive game systems, mechanics, tools, and experiences for players.', array['Game Programming','Unity or Unreal Engine','Computer Graphics','Game Design']),
('devops', 'DevOps Engineer', 'Automates software delivery and keeps development, deployment, and operations reliable.', array['CI/CD Pipelines','Docker and Kubernetes','Linux Administration','Infrastructure as Code']),
('systems_analyst', 'Systems Analyst', 'Studies organizational systems and designs practical improvements to processes and technology.', array['Systems Analysis and Design','Requirements Engineering','Database Systems','Project Management']),
('qa_automation', 'Software QA/Test Automation Engineer', 'Tests applications, finds defects, writes test cases, and automates quality checks before release.', array['Software Testing Fundamentals','Selenium WebDriver','Unit Testing','Test Automation Frameworks'])
on conflict (slug) do update set
    name = excluded.name,
    description = excluded.description,
    suggested_courses = excluded.suggested_courses;
