(function() {
    'use strict';

    const ENHANCED_CLASS = 'table-keyboard-scroll-ready';
    const GENERATED_WRAPPER_CLASS = 'table-keyboard-scroll-wrapper';
    const STYLE_ID = 'table-keyboard-scroll-style';
    const SCROLL_KEYS = new Set(['ArrowLeft', 'ArrowRight']);

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return;

        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
            .${ENHANCED_CLASS} {
                scroll-behavior: smooth;
            }
            .${ENHANCED_CLASS}:focus {
                outline: 2px solid rgba(13, 110, 253, 0.35);
                outline-offset: 2px;
            }
        `;
        document.head.appendChild(style);
    }

    function isTypingTarget(element) {
        if (!element) return false;
        const tagName = element.tagName ? element.tagName.toLowerCase() : '';
        return tagName === 'input'
            || tagName === 'select'
            || tagName === 'textarea'
            || element.isContentEditable;
    }

    function isScrollable(element) {
        return element && element.scrollWidth > element.clientWidth + 4;
    }

    function isVisible(element) {
        if (!element) return false;
        const rect = element.getBoundingClientRect();
        return rect.width > 0
            && rect.height > 0
            && rect.bottom > 0
            && rect.top < window.innerHeight
            && rect.right > 0
            && rect.left < window.innerWidth;
    }

    function enhanceContainer(container) {
        if (!container || container.dataset.keyboardScrollEnhanced === 'true') return;

        container.dataset.keyboardScrollEnhanced = 'true';
        container.classList.add(ENHANCED_CLASS);
        if (!container.hasAttribute('tabindex')) {
            container.setAttribute('tabindex', '0');
        }
        if (!container.hasAttribute('aria-label')) {
            container.setAttribute('aria-label', 'Area tabel, gunakan tombol panah kiri dan kanan untuk menggeser tabel');
        }
        if (!container.hasAttribute('title')) {
            container.setAttribute('title', 'Gunakan tombol panah kiri dan kanan untuk menggeser tabel');
        }
    }

    function wrapOverflowTable(table) {
        if (!table || table.closest('.table-responsive')) return;

        const parent = table.parentElement;
        if (!parent || parent.classList.contains(GENERATED_WRAPPER_CLASS)) return;

        const parentWidth = parent.clientWidth || window.innerWidth;
        if (table.scrollWidth <= parentWidth + 4) return;

        const wrapper = document.createElement('div');
        wrapper.className = `table-responsive ${GENERATED_WRAPPER_CLASS}`;
        parent.insertBefore(wrapper, table);
        wrapper.appendChild(table);
        enhanceContainer(wrapper);
    }

    function enhanceTables() {
        injectStyles();
        document.querySelectorAll('.table-responsive').forEach(enhanceContainer);
        document.querySelectorAll('table').forEach(wrapOverflowTable);
    }

    function getVisibleScore(element) {
        const rect = element.getBoundingClientRect();
        const visibleTop = Math.max(rect.top, 0);
        const visibleBottom = Math.min(rect.bottom, window.innerHeight);
        const visibleHeight = Math.max(visibleBottom - visibleTop, 0);
        const viewportCenter = window.innerHeight / 2;
        const elementCenter = rect.top + rect.height / 2;
        return visibleHeight - Math.abs(elementCenter - viewportCenter) * 0.05;
    }

    function findTargetContainer(eventTarget) {
        const activeContainer = eventTarget && eventTarget.closest
            ? eventTarget.closest('.table-responsive')
            : null;
        if (activeContainer && isScrollable(activeContainer) && isVisible(activeContainer)) {
            return activeContainer;
        }

        let selected = null;
        let selectedScore = Number.NEGATIVE_INFINITY;
        document.querySelectorAll('.table-responsive').forEach((container) => {
            if (!isScrollable(container) || !isVisible(container)) return;

            const score = getVisibleScore(container);
            if (score > selectedScore) {
                selected = container;
                selectedScore = score;
            }
        });

        return selected;
    }

    function scrollContainer(container, direction) {
        if (!container) return false;

        const before = container.scrollLeft;
        const step = Math.max(180, Math.round(container.clientWidth * 0.45));
        container.scrollBy({ left: direction * step, behavior: 'smooth' });
        return container.scrollLeft !== before
            || (direction > 0 && container.scrollLeft + container.clientWidth < container.scrollWidth)
            || (direction < 0 && container.scrollLeft > 0);
    }

    function handleKeydown(event) {
        if (!SCROLL_KEYS.has(event.key)) return;
        if (document.body.classList.contains('modal-open')) return;
        if (isTypingTarget(event.target)) return;

        const container = findTargetContainer(event.target);
        if (!container) return;

        const direction = event.key === 'ArrowRight' ? 1 : -1;
        if (scrollContainer(container, direction)) {
            event.preventDefault();
        }
    }

    function observeDynamicTables() {
        if (!window.MutationObserver) return;

        const observer = new MutationObserver(() => {
            window.requestAnimationFrame(enhanceTables);
        });
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    function init() {
        enhanceTables();
        observeDynamicTables();
        document.addEventListener('keydown', handleKeydown);
        window.addEventListener('resize', enhanceTables);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
