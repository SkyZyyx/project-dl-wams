(function() {
    var AUTH_TOKEN_KEY = "auth_access_token";
    var AUTH_ROLE_KEY = "auth_user_role";

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>\"']/g, function(char) {
            return ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;"
            })[char];
        });
    }

    function formatPrice(value) {
        if (value === null || value === undefined || value === "") {
            return "Price on request";
        }

        var numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return String(value);
        }

        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 2
        }).format(numeric);
    }

    function formatScore(value) {
        var score = Number(value || 0);
        return Number.isFinite(score) ? score.toFixed(3) : "0.000";
    }

    function formatSimilarity(value) {
        var score = Number(value || 0);
        if (!Number.isFinite(score)) {
            return "0%";
        }
        return Math.round(score * 100) + "%";
    }

    function imageSource(product) {
        var images = product && product.images ? product.images : [];
        if (!images.length) {
            return "";
        }

        var image = images[0] || {};
        if (image.image_url) {
            return image.image_url;
        }

        if (image.thumbnail_b64) {
            return "data:image/jpeg;base64," + image.thumbnail_b64;
        }

        return "";
    }

    function productImages(product) {
        return ((product && product.images) || []).map(function(image) {
            if (image.image_url) {
                return image.image_url;
            }
            if (image.thumbnail_b64) {
                return "data:image/jpeg;base64," + image.thumbnail_b64;
            }
            return "";
        }).filter(Boolean);
    }

    function renderProductCard(product, options) {
        var config = options || {};
        var article = document.createElement("article");
        article.className = "product-card" + (config.featured ? " is-featured" : "");
        article.setAttribute("data-product-id", product.id || "");

        var media = document.createElement("div");
        media.className = "product-media";
        var source = imageSource(product);

        if (source) {
            var image = document.createElement("img");
            image.loading = "lazy";
            image.alt = product.name || "Product image";
            image.src = source;
            media.appendChild(image);
        } else {
            var fallback = document.createElement("div");
            fallback.className = "fallback";
            fallback.textContent = (product.name || "").slice(0, 2).toUpperCase() || "•";
            media.appendChild(fallback);
        }

        var badgeRow = document.createElement("div");
        badgeRow.className = "meta-row";

        var typeBadge = document.createElement("span");
        typeBadge.className = "product-badge";
        typeBadge.textContent = product.category && product.category.name ? product.category.name : "Curated";
        badgeRow.appendChild(typeBadge);

        if (config.showScore && product.score !== undefined && product.score !== null) {
            var scoreBadge = document.createElement("span");
            scoreBadge.className = "score-badge";
            scoreBadge.textContent = "Similarity " + formatSimilarity(product.score);
            scoreBadge.title = "Raw confidence score: " + formatScore(product.score);
            badgeRow.appendChild(scoreBadge);
        }

        var title = document.createElement("h4");
        title.className = "product-title";
        title.textContent = product.name || "Untitled product";

        var copy = document.createElement("p");
        copy.className = "product-copy";
        copy.textContent = product.description || "Clean lines, ready for the shelf.";

        var footer = document.createElement("div");
        footer.className = "product-footer";

        var price = document.createElement("strong");
        price.className = "price";
        price.textContent = formatPrice(product.price);

        var idChip = document.createElement("span");
        idChip.className = "mini-badge";
        idChip.textContent = product.id ? "SKU " + product.id : "In stock";

        footer.appendChild(price);
        footer.appendChild(idChip);

        article.appendChild(media);
        article.appendChild(badgeRow);
        article.appendChild(title);
        article.appendChild(copy);
        article.appendChild(footer);

        if (typeof config.onSelect === "function") {
            article.tabIndex = 0;
            article.style.cursor = "pointer";
            article.addEventListener("click", function() {
                config.onSelect(product, article);
            });
            article.addEventListener("keydown", function(event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    config.onSelect(product, article);
                }
            });
        }

        if (config.href) {
            article.addEventListener("click", function(event) {
                if (event.target.closest("button, a, input, textarea, select, label")) {
                    return;
                }
                window.location.href = config.href.replace("__ID__", encodeURIComponent(product.id));
            });
        }

        return article;
    }

    function renderProductGrid(container, items, options) {
        var list = Array.isArray(items) ? items : [];
        var config = options || {};
        container.innerHTML = "";

        if (!list.length) {
            var empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = config.emptyMessage || "No products to show yet.";
            container.appendChild(empty);
            return;
        }

        list.forEach(function(item) {
            container.appendChild(renderProductCard(item, config));
        });
    }

    function setStatus(el, tone, title, detail) {
        if (!el) {
            return;
        }

        el.dataset.tone = tone || "info";
        el.innerHTML = "<strong>" + escapeHtml(title || "Status") + "</strong>" + (detail ? "<div class=\"status-copy\">" + escapeHtml(detail) + "</div>" : "");
    }

    function normalizeRole(role) {
        var value = String(role || "").trim().toLowerCase();
        if (value === "admin" || value === "seller" || value === "client") {
            return value;
        }
        return "";
    }

    function hasToken() {
        return !!getAuthToken();
    }

    function getAuthToken() {
        return localStorage.getItem(AUTH_TOKEN_KEY) || "";
    }

    function getStoredRole() {
        return normalizeRole(localStorage.getItem(AUTH_ROLE_KEY) || "");
    }

    function emitSessionChanged() {
        window.dispatchEvent(new Event("wams:session-changed"));
    }

    function setAuthSession(token, role) {
        var tokenValue = String(token || "").trim();
        var roleValue = normalizeRole(role);

        if (tokenValue) {
            localStorage.setItem(AUTH_TOKEN_KEY, tokenValue);
        } else {
            localStorage.removeItem(AUTH_TOKEN_KEY);
        }

        if (roleValue) {
            localStorage.setItem(AUTH_ROLE_KEY, roleValue);
        } else {
            localStorage.removeItem(AUTH_ROLE_KEY);
        }

        emitSessionChanged();
    }

    function clearAuthSession() {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_ROLE_KEY);
        emitSessionChanged();
    }

    function roleLabel(role) {
        var value = normalizeRole(role);
        if (!value) {
            return "";
        }
        return value.charAt(0).toUpperCase() + value.slice(1);
    }

    function isInvalidTokenMessage(message) {
        var value = String(message || "").toLowerCase();
        return value.indexOf("unauthorized") >= 0
            || value.indexOf("given token not valid") >= 0
            || value.indexOf("token not valid") >= 0
            || value.indexOf("token is invalid") >= 0;
    }

    async function fetchAuthProfile(token) {
        var authToken = String(token || "").trim();
        if (!authToken) {
            throw new Error("No access token available.");
        }
        return fetchJson("/api/auth/profile/", {
            method: "GET",
            headers: {
                Authorization: "Bearer " + authToken,
                Accept: "application/json"
            }
        });
    }

    function updateRoleBadge() {
        var badge = document.getElementById("role-badge");
        var valueEl = document.getElementById("role-badge-value");
        if (!badge || !valueEl) {
            return;
        }

        var token = getAuthToken();
        var role = getStoredRole();
        if (!token || !role) {
            badge.hidden = true;
            badge.removeAttribute("data-role");
            valueEl.textContent = "";
            return;
        }

        badge.hidden = false;
        badge.setAttribute("data-role", role);
        valueEl.textContent = roleLabel(role);
    }

    function updateNavLinks() {
        var loginLink = document.getElementById("nav-login");
        var registerLink = document.getElementById("nav-register");
        var profileLink = document.getElementById("nav-profile");
        var dashboardLink = document.getElementById("nav-dashboard");
        var sellLink = document.getElementById("nav-sell");
        var logoutLink = document.getElementById("nav-logout");
        var authenticated = hasToken();
        var role = getStoredRole();

        if (loginLink) {
            loginLink.hidden = authenticated;
        }
        if (registerLink) {
            registerLink.hidden = authenticated;
        }
        if (profileLink) {
            profileLink.hidden = !authenticated;
        }
        if (dashboardLink) {
            dashboardLink.hidden = !authenticated || role !== "admin";
        }
        if (sellLink) {
            sellLink.hidden = !authenticated || (role !== "seller" && role !== "admin");
        }
        if (logoutLink) {
            logoutLink.hidden = !authenticated;
        }
    }

    async function hydrateRoleFromProfile() {
        var token = getAuthToken();
        var role = getStoredRole();
        if (!token || role) {
            return;
        }

        try {
            var profile = await fetchAuthProfile(token);
            var profileRole = normalizeRole(profile.role);
            if (profileRole) {
                setAuthSession(token, profileRole);
            }
        } catch (error) {
            if (isInvalidTokenMessage(error && error.message)) {
                clearAuthSession();
            }
        }
    }

    async function fetchJson(url, options) {
        var response = await fetch(url, options || {});
        var text = await response.text();
        var data = {};

        if (text) {
            try {
                data = JSON.parse(text);
            } catch (error) {
                data = { detail: text };
            }
        }

        if (!response.ok) {
            var detail = data && (data.detail || data.message || data.error);
            throw new Error(detail || ("Request failed (HTTP " + response.status + ")"));
        }

        return data;
    }

    async function fetchCollectionPage(url) {
        var response = await fetch(url, { headers: { Accept: "application/json" } });
        var text = await response.text();
        var data = {};

        if (text) {
            try {
                data = JSON.parse(text);
            } catch (error) {
                data = { detail: text };
            }
        }

        if (!response.ok) {
            var detail = data && (data.detail || data.message || data.error);
            throw new Error(detail || ("Request failed (HTTP " + response.status + ")"));
        }

        return data;
    }

    async function searchWithImage(file, threshold, limit) {
        var formData = new FormData();
        formData.append("image", file);
        formData.append("score_threshold", String(threshold));
        if (limit !== undefined && limit !== null && limit !== "") {
            formData.append("limit", String(limit));
        }
        return fetchJson("/api/search/", {
            method: "POST",
            body: formData
        });
    }

    async function loadCollection(endpoint) {
        var firstPayload = await fetchCollectionPage(endpoint);

        if (Array.isArray(firstPayload)) {
            return firstPayload;
        }

        if (!firstPayload || typeof firstPayload !== "object") {
            return [];
        }

        if (!Array.isArray(firstPayload.results)) {
            return [];
        }

        var items = firstPayload.results.slice();
        var nextUrl = firstPayload.next;
        var visited = {};

        while (nextUrl) {
            if (visited[nextUrl]) {
                break;
            }
            visited[nextUrl] = true;

            var pageUrl = nextUrl;
            if (pageUrl.indexOf("http://") !== 0 && pageUrl.indexOf("https://") !== 0) {
                pageUrl = new URL(pageUrl, window.location.href).toString();
            }

            var pagePayload = await fetchCollectionPage(pageUrl);
            if (!pagePayload || typeof pagePayload !== "object" || !Array.isArray(pagePayload.results)) {
                break;
            }

            items = items.concat(pagePayload.results);
            nextUrl = pagePayload.next;
        }

        return items;
    }

    async function fetchProductById(productId) {
        var items;
        if (productId === undefined || productId === null || productId === "") {
            throw new Error("Product id is required.");
        }
        items = await loadCollection("/api/products/?ids=" + encodeURIComponent(String(productId)));
        return items.length ? items[0] : null;
    }

    async function loadHealth() {
        return fetchJson("/api/health/", { headers: { Accept: "application/json" } });
    }

    window.addEventListener("wams:session-changed", function() {
        updateRoleBadge();
        updateNavLinks();
    });

    document.addEventListener("click", function(event) {
        var target = event.target && event.target.closest ? event.target.closest("#nav-logout") : null;
        if (!target) {
            return;
        }

        event.preventDefault();
        clearAuthSession();
        window.location.href = "/auth/login/";
    });

    updateRoleBadge();
    updateNavLinks();
    hydrateRoleFromProfile();

    window.WAMS = {
        authTokenKey: AUTH_TOKEN_KEY,
        authRoleKey: AUTH_ROLE_KEY,
        escapeHtml: escapeHtml,
        formatPrice: formatPrice,
        formatScore: formatScore,
        formatSimilarity: formatSimilarity,
        imageSource: imageSource,
        productImages: productImages,
        renderProductCard: renderProductCard,
        renderProductGrid: renderProductGrid,
        setStatus: setStatus,
        fetchJson: fetchJson,
        searchWithImage: searchWithImage,
        loadCollection: loadCollection,
        fetchProductById: fetchProductById,
        loadHealth: loadHealth,
        normalizeRole: normalizeRole,
        isInvalidTokenMessage: isInvalidTokenMessage,
        getAuthToken: getAuthToken,
        getStoredRole: getStoredRole,
        setAuthSession: setAuthSession,
        clearAuthSession: clearAuthSession,
        fetchAuthProfile: fetchAuthProfile,
        updateRoleBadge: updateRoleBadge,
        updateNavLinks: updateNavLinks
    };

    window.dispatchEvent(new Event("wams:ready"));
})();
