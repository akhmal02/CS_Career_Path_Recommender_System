document.querySelectorAll("[data-max-group]").forEach((input) => {
    input.addEventListener("change", () => {
        const group = input.name;
        const max = Number(input.dataset.maxGroup);
        const checked = document.querySelectorAll(`input[name="${group}"]:checked`);
        if (checked.length > max) {
            input.checked = false;
            window.alert(`Please select no more than ${max} options.`);
        }
    });
});

document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".tab, .tab-panel").forEach((item) => {
            item.classList.remove("active");
        });
        button.classList.add("active");
        document.getElementById(button.dataset.tab).classList.add("active");
    });
});

document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm("Are you sure you want to continue?")) {
            event.preventDefault();
        }
    });
});

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const field = button.closest(".password-field");
    const input = field ? field.querySelector("input") : null;
    if (!input) return;
    button.addEventListener("click", () => {
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.classList.toggle("is-visible", !showing);
        button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
});

document.querySelectorAll("[data-disable-on-submit]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button[type='submit']");
        if (button) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = "Please wait...";
        }
    });
});

const resetPasswordForm = document.querySelector("[data-reset-password-form]");
if (resetPasswordForm) {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const status = resetPasswordForm.querySelector("[data-reset-status]");
    if (accessToken && refreshToken) {
        resetPasswordForm.querySelector("[data-reset-access-token]").value = accessToken;
        resetPasswordForm.querySelector("[data-reset-refresh-token]").value = refreshToken;
        if (status) status.textContent = "Reset link verified. Enter and confirm your new password.";
    } else if (status) {
        status.textContent = "Reset tokens were not found. If this link came from email and still fails, request a new reset link.";
    }
}

const careerSearch = document.querySelector("[data-career-search]");
if (careerSearch) {
    const cards = [...document.querySelectorAll("[data-career-card]")];
    const status = document.querySelector("[data-search-status]");
    careerSearch.addEventListener("input", () => {
        const query = careerSearch.value.trim().toLowerCase();
        const nameMatches = cards.filter((card) => (card.dataset.careerName || "").toLowerCase().includes(query));
        const shouldPrioritiseNames = query.length > 0 && nameMatches.length > 0;
        let visible = 0;
        cards.forEach((card) => {
            const nameText = (card.dataset.careerName || "").toLowerCase();
            const searchText = (card.dataset.searchText || "").toLowerCase();
            const matches = !query || (shouldPrioritiseNames ? nameText.includes(query) : searchText.includes(query));
            card.hidden = !matches;
            if (matches) visible += 1;
        });
        status.textContent = query
            ? `${visible} career path${visible === 1 ? "" : "s"} found`
            : "";
    });
}

const careerSection = document.getElementById("careers");
const homeNavItem = document.querySelector('[data-nav-item="home"]');
const careersNavItem = document.querySelector('[data-nav-item="careers"]');
if (careerSection && homeNavItem && careersNavItem) {
    const setLandingNavState = () => {
        const sectionTop = careerSection.getBoundingClientRect().top;
        const careersVisible = sectionTop <= Math.min(window.innerHeight * 0.42, 320);
        homeNavItem.classList.toggle("active", !careersVisible);
        careersNavItem.classList.toggle("active", careersVisible);
    };

    setLandingNavState();
    window.addEventListener("scroll", setLandingNavState, { passive: true });
    window.addEventListener("resize", setLandingNavState);
    window.addEventListener("hashchange", setLandingNavState);
}

const chatbotPage = document.querySelector("[data-chatbot-page]");
if (chatbotPage) {
    const form = chatbotPage.querySelector("[data-chatbot-page-form]");
    const thread = chatbotPage.querySelector("[data-chatbot-thread]");
    const greeting = chatbotPage.querySelector("[data-chatbot-greeting-copy]");
    const input = form.querySelector("textarea[name='message']");
    const submitButton = form.querySelector("button[type='submit']");
    let isSubmitting = false;

    const updateSubmitState = () => {
        submitButton.disabled = isSubmitting || input.value.trim().length === 0;
    };

    const scrollToLatest = () => {
        thread.scrollTop = thread.scrollHeight;
    };

    const markConversationStarted = () => {
        chatbotPage.classList.add("conversation-started");
        if (greeting) greeting.setAttribute("aria-hidden", "true");
    };

    const autoResize = () => {
        input.style.height = "auto";
        input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    };

    input.addEventListener("input", () => {
        autoResize();
        updateSubmitState();
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!submitButton.disabled) form.requestSubmit();
        }
    });

    chatbotPage.querySelectorAll("[data-suggestion]").forEach((button) => {
        button.addEventListener("click", () => {
            input.value = button.dataset.suggestion;
            autoResize();
            updateSubmitState();
            form.requestSubmit();
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question || isSubmitting) return;

        const formData = new FormData(form);
        formData.set("message", question);
        markConversationStarted();
        addChatBubble(question, "user");
        input.value = "";
        autoResize();
        isSubmitting = true;
        updateSubmitState();
        const thinking = addChatBubble("Career Path Assistant is typing...", "bot loading");

        try {
            const response = await window.fetch("/chatbot/message", {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();
            thinking.remove();
            if (!response.ok || payload.error) {
                addChatBubble(payload.error || "Sorry, I could not process your request. Please try again.", "bot");
            } else {
                addChatBubble(payload.reply || "Sorry, I could not process your request. Please try again.", "bot", payload.source);
            }
        } catch (error) {
            thinking.remove();
            addChatBubble("Sorry, I could not process your request. Please try again.", "bot");
        } finally {
            isSubmitting = false;
            updateSubmitState();
            input.focus();
        }
    });

    function addChatBubble(text, type, source = "") {
        const bubble = document.createElement("article");
        bubble.className = `chat-bubble ${type}`;
        if (!type.includes("user")) {
            const avatar = document.createElement("span");
            avatar.className = "bot-avatar";
            avatar.setAttribute("aria-hidden", "true");
            avatar.textContent = "AI";
            bubble.appendChild(avatar);
        }
        const content = document.createElement("div");
        const author = document.createElement("strong");
        author.textContent = type.includes("user") ? "You" : "Career Path Assistant";
        const body = document.createElement("p");
        body.textContent = text;
        content.append(author, body);
        if (source && !type.includes("user") && !type.includes("loading")) {
            const sourceLabel = document.createElement("small");
            sourceLabel.className = "chat-source";
            sourceLabel.textContent = source === "gemini" ? "Answered by Gemini" : "Answered by offline fallback";
            content.appendChild(sourceLabel);
        }
        bubble.appendChild(content);
        thread.appendChild(bubble);
        scrollToLatest();
        return bubble;
    }

    autoResize();
    updateSubmitState();
    scrollToLatest();
}

const wizardForm = document.querySelector("[data-wizard-form]");
if (wizardForm) {
    const steps = [...wizardForm.querySelectorAll("[data-step-title]")];
    const progress = document.querySelector("[data-wizard-progress]");
    const label = document.querySelector("[data-step-label]");
    const back = wizardForm.querySelector("[data-wizard-back]");
    const next = wizardForm.querySelector("[data-wizard-next]");
    const submit = wizardForm.querySelector("[data-wizard-submit]");
    let currentStep = 0;

    wizardForm.querySelectorAll("[data-ai-helper]").forEach((helper) => {
        const category = helper.dataset.category;
        const textarea = helper.querySelector("textarea");
        const button = helper.querySelector("[data-ai-suggest]");
        const status = helper.querySelector("[data-ai-status]");
        if (!category || !textarea || !button || !status) return;

        button.addEventListener("click", async () => {
            const description = textarea.value.trim();
            if (description.length < 8) {
                status.textContent = "Write a little more detail first.";
                status.className = "ai-status warning";
                textarea.focus();
                return;
            }

            const token = wizardForm.querySelector("input[name='csrf_token']");
            const formData = new FormData();
            formData.set("csrf_token", token ? token.value : "");
            formData.set("category", category);
            formData.set("description", description);
            button.disabled = true;
            status.textContent = "Finding matching choices from your description...";
            status.className = "ai-status";

            try {
                const response = await window.fetch("/questionnaire/suggest-options", {
                    method: "POST",
                    body: formData,
                });
                const payload = await response.json();
                if (!response.ok || payload.error) {
                    status.textContent = payload.error || "Could not find a confident match. Please choose manually.";
                    status.className = "ai-status warning";
                    return;
                }

                const selectedCodes = payload.selected_codes || [];
                const checkboxes = [...wizardForm.querySelectorAll(`input[name="${category}"]`)];
                const validCodes = new Set(checkboxes.map((input) => input.value));
                checkboxes.forEach((input) => {
                    input.checked = selectedCodes.includes(input.value) && validCodes.has(input.value);
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                });

                if (selectedCodes.length) {
                    const source = payload.source === "gemini" ? "Matched from your description" : "Matched using local keyword support";
                    status.textContent = `${source}: ${selectedCodes.length} choice${selectedCodes.length === 1 ? "" : "s"} selected. Review before continuing. ${payload.explanation || ""}`;
                    status.className = "ai-status success";
                } else {
                    status.textContent = payload.explanation || "No strong match was found. Please choose manually.";
                    status.className = "ai-status warning";
                }
            } catch (error) {
                status.textContent = "Could not match the description right now. Please choose manually.";
                status.className = "ai-status warning";
            } finally {
                button.disabled = false;
            }
        });
    });

    const showStep = (index) => {
        currentStep = Math.max(0, Math.min(index, steps.length - 1));
        steps.forEach((step, stepIndex) => {
            step.classList.toggle("active", stepIndex === currentStep);
        });
        const percentage = ((currentStep + 1) / steps.length) * 100;
        progress.style.width = `${percentage}%`;
        label.textContent = `Step ${currentStep + 1} of ${steps.length}: ${steps[currentStep].dataset.stepTitle}`;
        back.disabled = currentStep === 0;
        next.hidden = currentStep === steps.length - 1;
        submit.hidden = currentStep !== steps.length - 1;
    };

    const stepIsValid = () => {
        const inputs = [...steps[currentStep].querySelectorAll("input[type='checkbox']")];
        if (!inputs.length) return true;
        const names = [...new Set(inputs.map((input) => input.name))];
        return names.every((name) => {
            const group = [...steps[currentStep].querySelectorAll(`input[name="${name}"]`)];
            const checked = group.filter((input) => input.checked);
            const max = Number(group[0].dataset.maxGroup || group.length);
            const minimums = {
                interests: 1,
                skills: 2,
                work_styles: 1,
                subjects: 1,
                goals: 1,
                activities: 1,
                priorities: 1,
            };
            const min = minimums[name] || 0;
            if (checked.length < min || checked.length > max) {
                window.alert(`Please select ${min} to ${max} option${max === 1 ? "" : "s"} before continuing.`);
                return false;
            }
            return true;
        });
    };

    next.addEventListener("click", () => {
        if (stepIsValid()) showStep(currentStep + 1);
    });
    back.addEventListener("click", () => showStep(currentStep - 1));
    wizardForm.addEventListener("submit", (event) => {
        if (!stepIsValid()) {
            event.preventDefault();
            return;
        }
        const loader = document.querySelector("[data-prediction-loader]");
        const message = document.querySelector("[data-loader-message]");
        const messages = [
            "Predicting your best career path",
            "Finding your strongest CS career signals",
            "Comparing your profile with career rules",
            "Preparing your recommendation report",
        ];
        let index = 0;
        if (loader && message) {
            loader.classList.add("show");
            loader.setAttribute("aria-hidden", "false");
            message.textContent = messages[index];
            window.setInterval(() => {
                index = (index + 1) % messages.length;
                message.textContent = messages[index];
            }, 1200);
        }
    });
    showStep(0);
}

const resultTabs = document.querySelector("[data-result-tabs]");
if (resultTabs) {
    const tabs = [...resultTabs.querySelectorAll("[data-result-tab]")];
    const panels = [...resultTabs.querySelectorAll("[data-result-panel]")];
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const active = tab.dataset.resultTab;
            tabs.forEach((item) => item.classList.toggle("active", item.dataset.resultTab === active));
            panels.forEach((item) => item.classList.toggle("active", item.dataset.resultPanel === active));
        });
    });
}

document.querySelectorAll("[data-ml-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        const panel = button.parentElement.querySelector("[data-ml-panel]");
        if (!panel) return;
        const isHidden = panel.hasAttribute("hidden");
        panel.toggleAttribute("hidden", !isHidden);
        button.textContent = isHidden ? "Hide calculation explanation" : "How this score is calculated";
    });
});
