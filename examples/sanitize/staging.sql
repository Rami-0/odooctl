-- Project-specific staging safety rules go here.
UPDATE ir_config_parameter SET value = 'https://staging-odoo.example.com' WHERE key = 'web.base.url';
