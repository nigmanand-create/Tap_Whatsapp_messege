frappe.pages['whatsapp-group-brows'].on_page_load = function(wrapper) {
    new WhatsAppGroupBrowser(wrapper);
}

class WhatsAppGroupBrowser {
    constructor(wrapper) {
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: 'Group Collections',
            single_column: true
        });
        
        this.$container = $(`<div class="wa-browser-container" style="padding: 15px; max-width: 1000px; margin: 0 auto;"></div>`).appendTo(this.page.main);
        
        this.setup_css();
        this.setup_actions();
        this.bind_route_events();
        
        this.state = {
            search_text: '',
            limit_start: 0,
            limit_page_length: 50,
            current_view: 'collections'
        };
        
        this.route();
    }
    
    setup_css() {
        if ($('#wa-browser-css').length) return;
        $(`<style id="wa-browser-css">
            .wa-card {
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                margin-bottom: 20px;
                overflow: hidden;
                border: 1px solid #e2e8f0;
            }
            .wa-search-bar {
                padding: 15px 20px;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
            }
            .wa-search-input {
                width: 100%;
                max-width: 300px;
                padding: 8px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                outline: none;
            }
            .wa-search-input:focus {
                border-color: #3b82f6;
                box-shadow: 0 0 0 1px #3b82f6;
            }
            .wa-list-header {
                display: flex;
                padding: 12px 20px;
                background: #f1f5f9;
                border-bottom: 1px solid #e2e8f0;
                font-size: 12px;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
            }
            .wa-list-item {
                display: flex;
                padding: 15px 20px;
                border-bottom: 1px solid #e2e8f0;
                transition: background 0.15s ease;
                align-items: center;
                cursor: pointer;
            }
            .wa-list-item:hover {
                background: #f8fafc;
            }
            .wa-list-item:last-child {
                border-bottom: none;
            }
            .wa-col-main {
                flex: 1;
                font-size: 14px;
                font-weight: 500;
                color: #1e293b;
            }
            .wa-col-meta {
                width: 150px;
                font-size: 13px;
                color: #64748b;
                text-align: right;
            }
            .wa-badge {
                color: #22c55e;
                font-weight: 500;
            }
            .wa-pagination {
                padding: 15px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #f8fafc;
                border-top: 1px solid #e2e8f0;
                font-size: 13px;
                color: #64748b;
            }
            .wa-page-btn {
                background: white;
                border: 1px solid #cbd5e1;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                color: #1e293b;
            }
            .wa-page-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .wa-empty-state {
                padding: 40px;
                text-align: center;
                color: #94a3b8;
            }
        </style>`).appendTo("head");
    }
    
    setup_actions() {
        this.page.set_primary_action('Sync With Glific', () => {
            this.trigger_sync();
        }, 'refresh');
    }
    
    trigger_sync() {
        let btn = this.page.btn_primary;
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Syncing...');
        
        frappe.call({
            method: "tap_buddy.api.whatsapp_browser.trigger_sync",
            callback: (r) => {
                btn.prop('disabled', false).html('<i class="fa fa-refresh"></i> Sync With Glific');
                if (r.message && r.message.status === 'success') {
                    frappe.show_alert({
                        message: __('Successfully synced {0} collections and {1} groups.', 
                            [r.message.collections_synced, r.message.groups_synced]),
                        indicator: 'green'
                    });
                    this.route(); // refresh the current view
                } else {
                    frappe.msgprint({
                        title: __('Sync Failed'),
                        indicator: 'red',
                        message: __('An unexpected error occurred during sync.')
                    });
                }
            },
            error: (r) => {
                btn.prop('disabled', false).html('<i class="fa fa-refresh"></i> Sync With Glific');
            }
        });
    }

    bind_route_events() {
        frappe.router.on('change', () => {
            if (frappe.get_route()[0] === 'whatsapp-group-brows') {
                this.route();
            }
        });
    }
    
    route() {
        let url = new URL(window.location.href);
        let collection_id = url.searchParams.get('collection');
        
        // Reset state on route change if switching views
        let new_view = collection_id ? 'details' : 'collections';
        if (this.state.current_view !== new_view) {
            this.state.search_text = '';
            this.state.limit_start = 0;
            this.state.current_view = new_view;
        }
        
        if (new_view === 'details') {
            this.render_collection_details(collection_id);
        } else {
            this.render_collections_list();
        }
    }
    
    set_route_param(key, value) {
        let url = new URL(window.location.href);
        if (value) {
            url.searchParams.set(key, value);
        } else {
            url.searchParams.delete(key);
        }
        window.history.pushState({}, '', url);
        this.route();
    }
    
    render_collections_list() {
        this.page.set_title('Group Collections');
        this.page.clear_inner_toolbar();
        
        this.$container.html(`
            <div class="wa-card">
                <div class="wa-search-bar">
                    <input type="text" class="wa-search-input" placeholder="Search collections..." value="${this.state.search_text}">
                </div>
                <div class="wa-list-header">
                    <div class="wa-col-main">Title</div>
                    <div class="wa-col-meta">Groups</div>
                </div>
                <div class="wa-list-body">
                    <div class="wa-empty-state"><i class="fa fa-spinner fa-spin"></i> Loading...</div>
                </div>
                <div class="wa-pagination">
                    <span class="wa-page-info"></span>
                    <div>
                        <button class="wa-page-btn btn-prev">Previous</button>
                        <button class="wa-page-btn btn-next" style="margin-left: 10px;">Next</button>
                    </div>
                </div>
            </div>
        `);
        
        this.bind_search_and_pagination(() => this.fetch_collections());
        this.fetch_collections();
    }
    
    fetch_collections() {
        frappe.call({
            method: "tap_buddy.api.whatsapp_browser.get_collections",
            args: {
                search_text: this.state.search_text,
                limit_start: this.state.limit_start,
                limit_page_length: this.state.limit_page_length
            },
            callback: (r) => {
                if (r.message) {
                    this.update_collections_dom(r.message.data, r.message.total);
                }
            }
        });
    }
    
    update_collections_dom(data, total) {
        let $body = this.$container.find('.wa-list-body');
        $body.empty();
        
        if (data.length === 0) {
            $body.html(`<div class="wa-empty-state">No collections found.</div>`);
        } else {
            data.forEach(col => {
                let $item = $(`
                    <div class="wa-list-item" data-id="${col.collection_id}">
                        <div class="wa-col-main">${col.name}</div>
                        <div class="wa-col-meta"><span class="wa-badge">${col.group_count} groups</span></div>
                    </div>
                `).appendTo($body);
                
                $item.on('click', () => {
                    this.set_route_param('collection', col.collection_id);
                });
            });
        }
        
        this.update_pagination_ui(data.length, total);
    }
    
    render_collection_details(collection_id) {
        this.page.set_title('Loading...');
        
        // Add back button to toolbar
        this.page.clear_inner_toolbar();
        this.page.add_inner_button('← Back to Collections', () => {
            this.set_route_param('collection', null);
        });
        
        this.$container.html(`
            <div class="wa-card">
                <div class="wa-search-bar">
                    <input type="text" class="wa-search-input" placeholder="Search groups..." value="${this.state.search_text}">
                </div>
                <div class="wa-list-header">
                    <div class="wa-col-main">Group Name</div>
                    <div class="wa-col-meta" style="text-align: left;">Last Communication</div>
                </div>
                <div class="wa-list-body">
                    <div class="wa-empty-state"><i class="fa fa-spinner fa-spin"></i> Loading...</div>
                </div>
                <div class="wa-pagination">
                    <span class="wa-page-info"></span>
                    <div>
                        <button class="wa-page-btn btn-prev">Previous</button>
                        <button class="wa-page-btn btn-next" style="margin-left: 10px;">Next</button>
                    </div>
                </div>
            </div>
        `);
        
        this.bind_search_and_pagination(() => this.fetch_collection_details(collection_id));
        this.fetch_collection_details(collection_id);
    }
    
    fetch_collection_details(collection_id) {
        frappe.call({
            method: "tap_buddy.api.whatsapp_browser.get_collection_details",
            args: {
                collection_id: collection_id,
                search_text: this.state.search_text,
                limit_start: this.state.limit_start,
                limit_page_length: this.state.limit_page_length
            },
            callback: (r) => {
                if (r.message) {
                    this.page.set_title(r.message.collection_name || 'Collection Details');
                    this.update_groups_dom(r.message.data, r.message.total);
                }
            }
        });
    }
    
    update_groups_dom(data, total) {
        let $body = this.$container.find('.wa-list-body');
        $body.empty();
        
        if (data.length === 0) {
            $body.html(`<div class="wa-empty-state">No groups found in this collection.</div>`);
        } else {
            data.forEach(grp => {
                let comm = grp.last_communication_at ? frappe.datetime.global_date_format(grp.last_communication_at) : 'N/A';
                
                let $item = $(`
                    <div class="wa-list-item" style="cursor: default;">
                        <div class="wa-col-main">${grp.group_name}</div>
                        <div class="wa-col-meta" style="text-align: left; color: #94a3b8;">${comm}</div>
                    </div>
                `).appendTo($body);
            });
        }
        
        this.update_pagination_ui(data.length, total);
    }
    
    bind_search_and_pagination(fetch_fn) {
        let me = this;
        let debounce_timer;
        
        this.$container.find('.wa-search-input').on('input', function() {
            me.state.search_text = $(this).val();
            me.state.limit_start = 0; // reset page on search
            
            clearTimeout(debounce_timer);
            debounce_timer = setTimeout(() => {
                fetch_fn();
            }, 300);
        });
        
        this.$container.find('.btn-prev').on('click', () => {
            if (this.state.limit_start >= this.state.limit_page_length) {
                this.state.limit_start -= this.state.limit_page_length;
                fetch_fn();
            }
        });
        
        this.$container.find('.btn-next').on('click', () => {
            this.state.limit_start += this.state.limit_page_length;
            fetch_fn();
        });
    }
    
    update_pagination_ui(current_count, total) {
        let start = this.state.limit_start + 1;
        let end = this.state.limit_start + current_count;
        if (current_count === 0) {
            start = 0;
            end = 0;
        }
        
        this.$container.find('.wa-page-info').text(`Showing ${start}-${end} of ${total}`);
        
        this.$container.find('.btn-prev').prop('disabled', this.state.limit_start === 0);
        this.$container.find('.btn-next').prop('disabled', (this.state.limit_start + this.state.limit_page_length) >= total);
    }
}