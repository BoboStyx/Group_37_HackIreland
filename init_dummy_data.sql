-- Drop existing tables if they exist
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS agent_tasks;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS user_profiles;

-- Create tables
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_input TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    model_used VARCHAR(50) NOT NULL,
    timestamp DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    meta_data TEXT
);

CREATE TABLE agent_tasks (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    task_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6),
    result TEXT
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    description TEXT NOT NULL,
    urgency INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    alertAt DATETIME(6)
);

CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    raw_input TEXT NOT NULL,
    structured_profile TEXT NOT NULL
);

-- Insert dummy conversations
INSERT INTO conversations (user_input, agent_response, model_used, timestamp, meta_data) VALUES
('Can you help me prioritize my tasks?', 'I''ll help you organize your tasks by urgency. Let''s start with the most critical ones.', 'gpt-4', NOW() - INTERVAL 2 DAY, '{"session_id": "abc123"}'),
('What''s on my schedule for today?', 'You have 3 high-priority tasks and 2 medium-priority tasks. Would you like me to go through them?', 'gpt-4', NOW() - INTERVAL 1 DAY, '{"session_id": "abc124"}'),
('Tell me about my project deadlines', 'I see several upcoming deadlines. The most urgent is the client presentation due tomorrow.', 'gpt-4', NOW() - INTERVAL 12 HOUR, '{"session_id": "abc125"}');

-- Insert dummy agent tasks
INSERT INTO agent_tasks (task_type, status, created_at, completed_at, result) VALUES
('task_summary', 'completed', NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY, 'Successfully summarized 15 tasks'),
('deep_analysis', 'completed', NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY, 'Completed analysis of project requirements'),
('reminder_setup', 'pending', NOW() - INTERVAL 1 DAY, NULL, NULL);

-- Insert dummy tasks with various urgency levels and statuses
INSERT INTO tasks (description, urgency, status, alertAt) VALUES
-- Urgency Level 5 (Highest)
('Client presentation for major account - Prepare comprehensive slides and demo for Acme Corp''s $2M cloud migration project. Key points: Current infrastructure analysis, proposed solution architecture, cost-benefit analysis, and implementation timeline. CEO and CTO will be present. Required: Working demo of the automated deployment pipeline. Follow up with Sarah from Sales for client-specific requirements. Meeting Room: A1, Floor 3.', 
5, 'pending', NOW() + INTERVAL 1 DAY),

('Critical security patch deployment - Urgent: Multiple critical vulnerabilities (CVE-2024-1234, CVE-2024-1235) found in production Kubernetes clusters. Affects: payment processing system and user authentication services. Impact: Potential data breach risk. Required: Coordinate with Security team (lead: John) for testing, prepare rollback plan, update dependency lists. Estimated downtime: 20 minutes. Must be done during off-peak hours (2-4 AM).', 
5, 'pending', NOW() + INTERVAL 4 HOUR),

('Emergency server maintenance - Production database cluster showing signs of failure. Symptoms: Increased latency (>500ms), sporadic 5xx errors (error rate: 2.3%). Affected services: User authentication, payment processing, order management. Current metrics: CPU: 92%, Memory: 87%, Disk: 95%. Required: Database replication check, log analysis, backup verification. Coordinate with: Database team (Mark), SRE team (Lisa). Customer Support has been notified.', 
5, 'pending', NOW() + INTERVAL 2 HOUR),

-- Urgency Level 4
('Quarterly report submission - Q4 2023 Technical Infrastructure Report. Sections needed: 1) System Performance Analysis (get metrics from Datadog), 2) Major Incidents Summary (coordinate with SRE team), 3) Cost Optimization Results (cloud spending reduced by 23%), 4) Upcoming Infrastructure Projects, 5) Team Growth & Training. Required: Executive summary, cost projections for Q1 2024, and resource allocation recommendations. Review with Director (James) before submission.', 
4, 'half-completed', NOW() + INTERVAL 3 DAY),

('Team performance reviews - Complete annual performance evaluations for development team (12 members). Areas to cover: Technical skills assessment, project contributions, collaboration metrics, OKR completion rates, and growth areas. Required: Individual 1:1 meetings (30 mins each), skill matrix updates, compensation recommendations. Coordinate with HR (Emily) for updated evaluation templates. Development plans must align with 2024 department goals.', 
4, 'pending', NOW() + INTERVAL 5 DAY),

('Product launch preparation - New API Gateway Release (v2.5.0). Features: GraphQL support, improved rate limiting, custom plugin architecture. Tasks: 1) Finish integration tests (current coverage: 87%), 2) Update API documentation, 3) Prepare migration guide, 4) Configure monitoring dashboards, 5) Update load balancer settings. Coordinate with: QA team (Alex), Documentation (Sarah), DevOps (Mike). Required: Staging environment demo for stakeholders.', 
4, 'pending', NOW() + INTERVAL 7 DAY),

-- Urgency Level 3
('Update documentation - Comprehensive update of microservices architecture documentation. Scope: 1) Service interaction diagrams, 2) API contracts, 3) Deployment workflows, 4) Monitoring setup, 5) Incident response procedures. Include: Performance benchmarks, scaling policies, and disaster recovery procedures. Tools: Confluence, Mermaid.js for diagrams. Review with: Architecture team (weekly sync, Thursdays 2 PM). Current completion: 45%.', 
3, 'pending', NOW() + INTERVAL 10 DAY),

('Code review for new feature - Review implementation of real-time analytics processing pipeline. Components: Kafka streams, Elasticsearch clustering, custom aggregation functions. Files changed: 47 files (+2,890, -750). Key areas: Data validation, error handling, performance optimizations. Check for: Memory leaks, connection pooling, retry mechanisms. Created by: David (Senior Dev). Branch: feature/realtime-analytics-pipeline.', 
3, 'half-completed', NOW() + INTERVAL 4 DAY),

('Client feedback implementation - Address feedback from beta testing of mobile app v3.2. Priority items: 1) Push notification delays (avg 45s, target <5s), 2) Offline mode data sync issues, 3) Battery optimization (current drain: 12%/hour), 4) UI responsiveness in chat module. Impact: 15K beta users. Required: A/B testing setup, analytics integration, crash reporting. Coordinate with: Mobile team (Tom), UX team (Anna).', 
3, 'pending', NOW() + INTERVAL 6 DAY),

-- Urgency Level 2
('Research new technologies - Evaluate emerging technologies for 2024 tech stack upgrades. Focus areas: 1) Edge computing solutions (Cloudflare Workers vs Fastly), 2) AI/ML model deployment options, 3) Container orchestration alternatives, 4) Serverless architectures. Deliverables: Comparison matrix, POC results, cost analysis, migration complexity assessment. Share findings in Tech All-Hands (Monthly, last Friday).', 
2, 'pending', NOW() + INTERVAL 14 DAY),

('Team building activity planning - Organize Q1 2024 team building event for Engineering department (45 people). Requirements: Technical workshop component (suggestions: System Design Workshop, Hackathon, Architecture Review), team dinner, activity options for remote participants. Budget: $5000. Location options: Tech Hub (capacity 60) or Innovation Center (capacity 50). Coordinate with: Office Manager (Jessica), Team Leads.', 
2, 'pending', NOW() + INTERVAL 20 DAY),

('Optional training session - Prepare advanced Kubernetes workshop for team. Topics: Custom controllers, Operators framework, GitOps workflows, Service mesh implementation. Format: 3-hour hands-on session, include exercises. Prerequisites: Basic K8s knowledge, cluster access. Resources needed: Training cluster setup, example applications, troubleshooting guides. Target audience: Mid-level & Senior developers.', 
2, 'pending', NOW() + INTERVAL 25 DAY),

-- Urgency Level 1 (Lowest)
('Office decoration ideas - Collect and implement ideas for new engineering floor layout. Focus: Collaboration spaces, quiet zones, meeting pods. Current issues: Limited whiteboard space, poor video call areas, insufficient power outlets. Budget: $3000. Gather feedback from: Team leads, remote workers on their office day needs. Consider: Standing desks, acoustic treatments, cable management solutions.', 
1, 'pending', NOW() + INTERVAL 30 DAY),

('Archive old project files - Clean up and archive completed projects from 2023. Projects: Legacy API (deprecated), Mobile App v2, Old CI/CD pipelines. Tasks: 1) Identify dependencies, 2) Document architecture decisions, 3) Archive to cold storage, 4) Update wiki. Storage usage: Currently at 85% capacity. Coordinate with: Infrastructure team for storage optimization. Required: Maintain compliance with data retention policy.', 
1, 'pending', NOW() + INTERVAL 45 DAY),

('Update personal development goals - Review and update personal development plans for 2024. Areas: 1) Technical skills (Focus: Distributed systems, AI/ML integration), 2) Leadership development, 3) Conference presentations, 4) Open source contributions. Include: Learning resources, certification plans, mentorship opportunities. Align with: Department OKRs, Career progression framework. Schedule quarterly check-ins with manager.', 
1, 'pending', NOW() + INTERVAL 60 DAY);

-- Insert dummy user profiles
INSERT INTO user_profiles (raw_input, structured_profile) VALUES
('I am a senior software engineer interested in AI and machine learning. I work on cloud infrastructure and enjoy solving complex problems.', 
'{"role": "Senior Software Engineer", "interests": ["AI", "Machine Learning", "Cloud Infrastructure"], "experience_years": 8, "preferred_notifications": "email"}'),

('Product manager with focus on user experience and agile methodologies. Looking to streamline our development process.',
'{"role": "Product Manager", "interests": ["UX", "Agile", "Process Improvement"], "experience_years": 5, "preferred_notifications": "slack"}'),

('DevOps engineer working on automation and deployment pipelines. Interested in security and performance optimization.',
'{"role": "DevOps Engineer", "interests": ["Automation", "Security", "Performance"], "experience_years": 6, "preferred_notifications": "both"}'); 