-- =============================================================================
-- CloudOrbit: Multi-Cloud Management Platform · PostgreSQL schema (reference)
-- -----------------------------------------------------------------------------
-- GENERATED from the SQLAlchemy models (backend/app/models) with the PostgreSQL
-- dialect. Alembic migrations (backend/alembic/versions) are the SOURCE OF TRUTH;
-- do not apply this file to a database managed by Alembic. Use instead:
--     cd backend && alembic upgrade head
-- Regenerate after any model change so this reference stays accurate.
-- =============================================================================

CREATE TABLE users (
	email VARCHAR(320) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	hashed_password VARCHAR(200) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	job_title VARCHAR(120), 
	timezone VARCHAR(64) NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE audit_logs (
	actor_id UUID, 
	actor_email VARCHAR(320), 
	action VARCHAR(80) NOT NULL, 
	target_type VARCHAR(40), 
	target_id VARCHAR(64), 
	status VARCHAR(10) NOT NULL, 
	details JSONB NOT NULL, 
	ip_address VARCHAR(64), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_audit_logs PRIMARY KEY (id), 
	CONSTRAINT fk_audit_logs_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_actor_id ON audit_logs (actor_id);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE INDEX ix_audit_logs_target_type ON audit_logs (target_type);

CREATE TABLE cloud_accounts (
	name VARCHAR(120) NOT NULL, 
	provider VARCHAR(10) NOT NULL, 
	external_id VARCHAR(128) NOT NULL, 
	default_region VARCHAR(64) NOT NULL, 
	description TEXT, 
	encrypted_credentials TEXT NOT NULL, 
	credential_hint VARCHAR(64), 
	credentials_rotated_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(20) NOT NULL, 
	status_message TEXT, 
	last_validated_at TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	is_active BOOLEAN NOT NULL, 
	provider_state JSONB NOT NULL, 
	created_by_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_cloud_accounts PRIMARY KEY (id), 
	CONSTRAINT uq_cloud_accounts_ext UNIQUE (provider, external_id), 
	CONSTRAINT fk_cloud_accounts_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_cloud_accounts_provider ON cloud_accounts (provider);

CREATE TABLE login_events (
	user_id UUID, 
	email VARCHAR(320) NOT NULL, 
	success BOOLEAN NOT NULL, 
	failure_reason VARCHAR(80), 
	ip_address VARCHAR(64), 
	user_agent VARCHAR(400), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_login_events PRIMARY KEY (id), 
	CONSTRAINT fk_login_events_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_login_events_created_at ON login_events (created_at);

CREATE INDEX ix_login_events_user_id ON login_events (user_id);

CREATE TABLE budgets (
	name VARCHAR(120) NOT NULL, 
	provider VARCHAR(10), 
	cloud_account_id UUID, 
	monthly_limit NUMERIC(14, 2) NOT NULL, 
	alert_threshold_percent INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_by_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_budgets PRIMARY KEY (id), 
	CONSTRAINT fk_budgets_cloud_account_id_cloud_accounts FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_budgets_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE cost_records (
	cloud_account_id UUID NOT NULL, 
	provider VARCHAR(10) NOT NULL, 
	service VARCHAR(80) NOT NULL, 
	period_month DATE NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_cost_records PRIMARY KEY (id), 
	CONSTRAINT uq_cost_records_key UNIQUE (cloud_account_id, service, period_month), 
	CONSTRAINT fk_cost_records_cloud_account_id_cloud_accounts FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts (id) ON DELETE CASCADE
);

CREATE INDEX ix_cost_records_cloud_account_id ON cost_records (cloud_account_id);

CREATE INDEX ix_cost_records_period_month ON cost_records (period_month);

CREATE INDEX ix_cost_records_provider ON cost_records (provider);

CREATE TABLE resources (
	cloud_account_id UUID NOT NULL, 
	provider VARCHAR(10) NOT NULL, 
	resource_type VARCHAR(40) NOT NULL, 
	external_id VARCHAR(255) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	region VARCHAR(64) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	attributes JSONB NOT NULL, 
	tags JSONB NOT NULL, 
	monthly_cost_estimate NUMERIC(12, 2) NOT NULL, 
	managed_by_platform BOOLEAN NOT NULL, 
	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_resources PRIMARY KEY (id), 
	CONSTRAINT uq_resources_account_ext UNIQUE (cloud_account_id, external_id), 
	CONSTRAINT fk_resources_cloud_account_id_cloud_accounts FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts (id) ON DELETE CASCADE
);

CREATE INDEX ix_resources_cloud_account_id ON resources (cloud_account_id);

CREATE INDEX ix_resources_provider ON resources (provider);

CREATE INDEX ix_resources_resource_type ON resources (resource_type);

CREATE INDEX ix_resources_status ON resources (status);

CREATE TABLE sync_jobs (
	cloud_account_id UUID NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	trigger VARCHAR(20) NOT NULL, 
	triggered_by_id UUID, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	resources_found INTEGER NOT NULL, 
	resources_created INTEGER NOT NULL, 
	resources_updated INTEGER NOT NULL, 
	resources_deleted INTEGER NOT NULL, 
	error TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_sync_jobs PRIMARY KEY (id), 
	CONSTRAINT fk_sync_jobs_cloud_account_id_cloud_accounts FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_sync_jobs_triggered_by_id_users FOREIGN KEY(triggered_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_sync_jobs_cloud_account_id ON sync_jobs (cloud_account_id);

CREATE TABLE alerts (
	severity VARCHAR(10) NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	message TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	fingerprint VARCHAR(200) NOT NULL, 
	cloud_account_id UUID, 
	resource_id UUID, 
	acknowledged_by_id UUID, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_alerts PRIMARY KEY (id), 
	CONSTRAINT fk_alerts_cloud_account_id_cloud_accounts FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_alerts_resource_id_resources FOREIGN KEY(resource_id) REFERENCES resources (id) ON DELETE CASCADE, 
	CONSTRAINT fk_alerts_acknowledged_by_id_users FOREIGN KEY(acknowledged_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_alerts_fingerprint ON alerts (fingerprint);

CREATE INDEX ix_alerts_severity ON alerts (severity);

CREATE INDEX ix_alerts_status ON alerts (status);

CREATE TABLE cost_alerts (
	budget_id UUID NOT NULL, 
	period_month DATE NOT NULL, 
	threshold_percent INTEGER NOT NULL, 
	actual_amount NUMERIC(14, 2) NOT NULL, 
	budget_limit NUMERIC(14, 2) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	acknowledged BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_cost_alerts PRIMARY KEY (id), 
	CONSTRAINT uq_cost_alerts_key UNIQUE (budget_id, period_month, threshold_percent), 
	CONSTRAINT fk_cost_alerts_budget_id_budgets FOREIGN KEY(budget_id) REFERENCES budgets (id) ON DELETE CASCADE
);

CREATE INDEX ix_cost_alerts_budget_id ON cost_alerts (budget_id);

CREATE TABLE provisioning_requests (
	cloud_account_id UUID NOT NULL, 
	action VARCHAR(10) NOT NULL, 
	template_key VARCHAR(64) NOT NULL, 
	resource_name VARCHAR(128) NOT NULL, 
	parameters JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	rendered_hcl TEXT NOT NULL, 
	plan_output TEXT NOT NULL, 
	plan_summary JSONB NOT NULL, 
	plan_is_mock BOOLEAN NOT NULL, 
	apply_output TEXT, 
	confirmation_token_hash VARCHAR(64), 
	confirmation_expires_at TIMESTAMP WITH TIME ZONE, 
	requested_by_id UUID, 
	confirmed_by_id UUID, 
	applied_at TIMESTAMP WITH TIME ZONE, 
	error TEXT, 
	target_resource_id UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_provisioning_requests PRIMARY KEY (id), 
	CONSTRAINT fk_provisioning_requests_cloud_account_id_cloud_accounts FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_provisioning_requests_requested_by_id_users FOREIGN KEY(requested_by_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_provisioning_requests_confirmed_by_id_users FOREIGN KEY(confirmed_by_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_provisioning_requests_target_resource_id_resources FOREIGN KEY(target_resource_id) REFERENCES resources (id) ON DELETE SET NULL
);

CREATE INDEX ix_provisioning_requests_cloud_account_id ON provisioning_requests (cloud_account_id);

CREATE INDEX ix_provisioning_requests_status ON provisioning_requests (status);

CREATE TABLE resource_changes (
	resource_id UUID NOT NULL, 
	change_type VARCHAR(20) NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	changes JSONB NOT NULL, 
	actor_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	CONSTRAINT pk_resource_changes PRIMARY KEY (id), 
	CONSTRAINT fk_resource_changes_resource_id_resources FOREIGN KEY(resource_id) REFERENCES resources (id) ON DELETE CASCADE, 
	CONSTRAINT fk_resource_changes_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_resource_changes_created_at ON resource_changes (created_at);

CREATE INDEX ix_resource_changes_resource_id ON resource_changes (resource_id);

CREATE TABLE resource_metrics (
	resource_id UUID NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	cpu_percent FLOAT, 
	memory_percent FLOAT, 
	network_in_mb FLOAT, 
	network_out_mb FLOAT, 
	storage_used_gb FLOAT, 
	id UUID NOT NULL, 
	CONSTRAINT pk_resource_metrics PRIMARY KEY (id), 
	CONSTRAINT fk_resource_metrics_resource_id_resources FOREIGN KEY(resource_id) REFERENCES resources (id) ON DELETE CASCADE
);

CREATE INDEX ix_resource_metrics_captured_at ON resource_metrics (captured_at);

CREATE INDEX ix_resource_metrics_resource_id ON resource_metrics (resource_id);
