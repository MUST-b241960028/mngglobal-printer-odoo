/** @odoo-module **/

import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { localization } from "@web/core/l10n/localization";
import { Wysiwyg } from "@html_editor/wysiwyg";
import { MAIN_PLUGINS, COLLABORATION_PLUGINS } from "@html_editor/plugin_sets";

const AUTOSAVE_DELAY = 1200;
const SEARCH_DELAY = 250;

export class TopicDialog extends Component {
    static template = "mngglobal_hub.TopicDialog";
    static components = { Dialog };
    static props = {
        title: String,
        topic: { type: Object, optional: true },
        categories: Array,
        programs: Array,
        periods: Array,
        onConfirm: Function,
        close: Function,
    };

    setup() {
        const topic = this.props.topic || {};
        this.state = useState({
            name: topic.name || "",
            summary: topic.summary || "",
            category_id: topic.category_id || false,
            program_type_id: topic.program_type_id || false,
            recruitment_period_id: topic.recruitment_period_id || false,
            error: "",
        });
    }

    onTextInput(field, event) {
        this.state[field] = event.target.value;
        this.state.error = "";
    }

    onSelectChange(field, event) {
        this.state[field] = event.target.value ? Number(event.target.value) : false;
    }

    async confirm() {
        const name = this.state.name.trim();
        if (!name) {
            this.state.error = "Сэдвийн нэрийг бичнэ үү.";
            return;
        }
        await this.props.onConfirm({
            name,
            summary: this.state.summary.trim(),
            category_id: this.state.category_id || false,
            program_type_id: this.state.program_type_id || false,
            recruitment_period_id: this.state.recruitment_period_id || false,
        });
        this.props.close();
    }
}

export class PageEditor extends Component {
    static template = "mngglobal_hub.PageEditor";
    static components = { Wysiwyg };
    static props = {
        page: Object,
        onEditorLoad: Function,
        onChange: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.editorConfig = {
            content: markup(this.props.page.body || ""),
            Plugins: [...MAIN_PLUGINS, ...COLLABORATION_PLUGINS],
            onChange: this.props.onChange,
            collaboration: {
                busService: this.env.services.bus_service,
                ormService: this.orm,
                collaborativeTrigger: "start",
                collaborationChannel: {
                    collaborationModelName: "mng.topic.page",
                    collaborationFieldName: "body",
                    collaborationResId: this.props.page.id,
                },
                peerId: Math.floor(Math.random() * Math.pow(2, 52)).toString(),
            },
            getRecordInfo: () => ({
                resModel: "mng.topic.page",
                resId: this.props.page.id,
            }),
            dropImageAsAttachment: true,
            direction: localization.direction || "ltr",
            baseContainers: ["DIV", "P"],
            placeholder: "Энэ сэдвээр дуудлага ирэхэд юу хэлэх ёстойгоо бичнэ үү...",
        };
    }
}

export class TopicHub extends Component {
    static template = "mngglobal_hub.TopicHub";
    static components = { PageEditor };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.dirty = false;
        this.editor = null;
        useAutofocus({ refName: "pageName", selectAll: true });
        this.draggedPageId = false;

        this.state = useState({
            loading: true,
            data: null,
            search: "",
            categoryId: false,
            topicId: false,
            page: null,
            pageLoading: false,
            saveState: "idle",
            savedLabel: "",
            renamingPage: false,
            navOpen: false,
        });

        this.autosave = useDebounced(() => this.savePage(), AUTOSAVE_DELAY, {
            execBeforeUnmount: true,
        });
        this.runSearch = useDebounced(() => this.load({ keepSelection: true }), SEARCH_DELAY);

        onWillStart(() => this.load());
    }

    // data

    async load({ keepSelection = false, selectTopicId = false } = {}) {
        this.state.loading = !this.state.data;
        const data = await this.orm.call("mng.topic", "get_hub_data", [this.state.search]);
        this.state.data = data;
        this.state.loading = false;

        if (this.state.categoryId && !data.categories.some((c) => c.id === this.state.categoryId)) {
            this.state.categoryId = false;
        }

        const wanted =
            selectTopicId ||
            (keepSelection && this.visibleTopics.some((t) => t.id === this.state.topicId)
                ? this.state.topicId
                : false);
        const topic = this.visibleTopics.find((t) => t.id === wanted) || this.visibleTopics[0];
        if (!topic) {
            this.state.topicId = false;
            this.state.page = null;
            return;
        }
        const samePage = topic.pages.some((p) => p.id === this.state.page?.id);
        this.state.topicId = topic.id;
        if (!samePage) {
            const target = topic.matches[0]?.page_id || topic.pages[0]?.id;
            await this.openPage(target);
        }
    }

    get visibleTopics() {
        const topics = this.state.data?.topics || [];
        if (!this.state.categoryId) {
            return topics;
        }
        return topics.filter((topic) => topic.category_id === this.state.categoryId);
    }

    get selectedTopic() {
        return this.state.data?.topics.find((t) => t.id === this.state.topicId) || null;
    }

    get pinnedTopics() {
        return this.visibleTopics.filter((topic) => topic.is_pinned);
    }

    get otherTopics() {
        return this.visibleTopics.filter((topic) => !topic.is_pinned);
    }

    get saveLabel() {
        return {
            idle: "",
            dirty: "Бичиж байна...",
            saving: "Хадгалж байна...",
            saved: `Хадгалагдсан ${this.state.savedLabel}`,
            error: "Хадгалагдсангүй",
        }[this.state.saveState];
    }

    // navigation

    async selectTopic(topicId) {
        if (this.state.topicId === topicId) {
            return;
        }
        await this.savePage();
        this.state.topicId = topicId;
        this.state.navOpen = false;
        const topic = this.state.data.topics.find((t) => t.id === topicId);
        await this.openPage(topic?.matches[0]?.page_id || topic?.pages[0]?.id);
    }

    async openPage(pageId) {
        if (!pageId) {
            this.state.page = null;
            return;
        }
        await this.savePage();
        this.state.pageLoading = true;
        this.state.renamingPage = false;
        this.state.saveState = "idle";
        this.editor = null;
        try {
            this.state.page = await this.orm.call("mng.topic.page", "get_page", [pageId]);
        } finally {
            this.state.pageLoading = false;
        }
    }

    async selectSearchHit(topicId, pageId) {
        this.state.topicId = topicId;
        this.state.navOpen = false;
        await this.openPage(pageId);
    }

    setCategory(categoryId) {
        this.state.categoryId = categoryId;
    }

    onSearchInput(event) {
        this.state.search = event.target.value;
        this.runSearch();
    }

    clearSearch() {
        this.state.search = "";
        this.runSearch();
    }

    toggleNav() {
        this.state.navOpen = !this.state.navOpen;
    }

    // editing

    onEditorLoad(editor) {
        this.editor = editor;
    }

    onEditorChange() {
        this.dirty = true;
        this.state.saveState = "dirty";
        this.autosave();
    }

    async savePage() {
        if (!this.dirty || !this.editor || this.editor.isDestroyed || !this.state.page) {
            return;
        }
        const pageId = this.state.page.id;
        const element = this.editor.getElContent();
        await this.editor.shared.imageSave?.savePendingImages(element);
        const content = element.innerHTML;
        this.dirty = false;
        this.state.saveState = "saving";
        try {
            await this.orm.write("mng.topic.page", [pageId], { body: content });
            this.state.page.body = content;
            this.state.saveState = "saved";
            this.state.savedLabel = new Date().toLocaleTimeString("mn-MN", {
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
            });
            const topic = this.selectedTopic;
            if (topic) {
                topic.edited_label = "Дөнгөж сая";
                topic.last_editor_name = this.state.data.current_user_name;
                const entry = topic.pages.find((item) => item.id === pageId);
                if (entry) {
                    entry.is_empty = !content.replace(/<[^>]*>/g, "").trim();
                }
            }
        } catch (error) {
            this.dirty = true;
            this.state.saveState = "error";
            throw error;
        }
    }

    // topics

    openTopicDialog(topic) {
        const data = this.state.data;
        this.dialog.add(TopicDialog, {
            title: topic ? "Сэдвийн тохиргоо" : "Шинэ сэдэв",
            topic,
            categories: data.all_categories,
            programs: data.programs,
            periods: data.periods,
            onConfirm: async (values) => {
                if (topic) {
                    await this.orm.write("mng.topic", [topic.id], values);
                    await this.load({ keepSelection: true });
                } else {
                    const [id] = await this.orm.create("mng.topic", [values]);
                    await this.load({ selectTopicId: id });
                }
            },
        });
    }

    async togglePin(topic) {
        await this.orm.write("mng.topic", [topic.id], { is_pinned: !topic.is_pinned });
        await this.load({ keepSelection: true });
    }

    archiveTopic(topic) {
        this.dialog.add(ConfirmationDialog, {
            title: "Сэдвийг архивлах",
            body: `"${topic.name}" сэдвийг архивлах уу? Менежер буцааж сэргээх боломжтой.`,
            confirmLabel: "Архивлах",
            cancelLabel: "Болих",
            confirm: async () => {
                await this.orm.call("mng.topic", "action_archive_topic", [[topic.id]]);
                this.state.topicId = false;
                this.state.page = null;
                await this.load();
            },
        });
    }

    // pages

    async addPage() {
        const topic = this.selectedTopic;
        if (!topic) {
            return;
        }
        await this.savePage();
        const lastSequence = topic.pages.at(-1)?.sequence || 0;
        const [pageId] = await this.orm.create("mng.topic.page", [
            { topic_id: topic.id, name: "Шинэ хуудас", sequence: lastSequence + 10 },
        ]);
        await this.load({ keepSelection: true });
        await this.openPage(pageId);
        this.startRenamePage();
    }

    startRenamePage() {
        this.state.renamingPage = true;
    }

    async commitRenamePage(event) {
        const name = event.target.value.trim();
        this.state.renamingPage = false;
        if (!name || name === this.state.page.name) {
            return;
        }
        await this.orm.write("mng.topic.page", [this.state.page.id], { name });
        this.state.page.name = name;
        const page = this.selectedTopic?.pages.find((p) => p.id === this.state.page.id);
        if (page) {
            page.name = name;
        }
    }

    onRenameKeydown(event) {
        if (event.key === "Enter") {
            event.target.blur();
        } else if (event.key === "Escape") {
            this.state.renamingPage = false;
        }
    }

    archivePage(page) {
        this.dialog.add(ConfirmationDialog, {
            title: "Хуудсыг архивлах",
            body: `"${page.name}" хуудсыг архивлах уу?`,
            confirmLabel: "Архивлах",
            cancelLabel: "Болих",
            confirm: async () => {
                try {
                    await this.orm.call("mng.topic.page", "action_archive_page", [[page.id]]);
                } catch (error) {
                    this.notification.add(
                        error.data?.message || "Хуудсыг архивлаж чадсангүй.",
                        { type: "danger" }
                    );
                    return;
                }
                this.state.page = null;
                await this.load({ keepSelection: true });
            },
        });
    }

    onPageDragStart(event, page) {
        this.draggedPageId = page.id;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(page.id));
    }

    allowPageDrop(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
    }

    async onPageDrop(event, target) {
        event.preventDefault();
        const draggedId = Number(event.dataTransfer.getData("text/plain") || this.draggedPageId);
        this.draggedPageId = false;
        const topic = this.selectedTopic;
        if (!draggedId || !topic || draggedId === target.id) {
            return;
        }
        const order = topic.pages.map((page) => page.id).filter((id) => id !== draggedId);
        order.splice(order.indexOf(target.id), 0, draggedId);
        await this.orm.call("mng.topic.page", "reorder", [order]);
        await this.load({ keepSelection: true });
    }
}

registry.category("actions").add("mngglobal_hub.topic_hub", TopicHub);
