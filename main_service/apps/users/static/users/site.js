(function () {
    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>\"']/g, function (char) {
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
            scoreBadge.textContent = "Match " + formatScore(product.score);
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

        list.forEach(function (item) {
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

    async function searchWithImage(file, threshold) {
        var formData = new FormData();
        formData.append("image", file);
        formData.append("score_threshold", String(threshold));
        return fetchJson("/api/search/", {
            method: "POST",
            body: formData
        });
    }

    async function gradcamWithImage(file) {
        var formData = new FormData();
        formData.append("image", file);
        return fetchJson("/api/gradcam/", {
            method: "POST",
            body: formData
        });
    }

    async function loadCollection(endpoint) {
        var response = await fetch(endpoint, { headers: { Accept: "application/json" } });
        var text = await response.text();
        var data = [];

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

        return Array.isArray(data) ? data : (data.results || []);
    }

    async function loadHealth() {
        return fetchJson("/api/health/", { headers: { Accept: "application/json" } });
    }

    window.WAMS = {
        escapeHtml: escapeHtml,
        formatPrice: formatPrice,
        formatScore: formatScore,
        imageSource: imageSource,
        renderProductCard: renderProductCard,
        renderProductGrid: renderProductGrid,
        setStatus: setStatus,
        fetchJson: fetchJson,
        searchWithImage: searchWithImage,
        gradcamWithImage: gradcamWithImage,
        loadCollection: loadCollection,
        loadHealth: loadHealth
    };

    window.dispatchEvent(new Event("wams:ready"));
})();
