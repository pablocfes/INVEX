var pathname = window.location.pathname;

var sidebar = {
    class: {
        body: {
            id: 'collapsed',
            name: 'sidebar-collapse'
        },
        navmenuv: {
            id: 'navmenuv',
            name: 'menu-is-opening'
        },
        navmenuvoption: {
            id: 'navmenuvoption',
        },
        navmenuvsingle: {
            id: 'navmenuvsingle',
        },
        navmenuhtab: {
            id: 'navmenuhtab'
        },
        navmenuh: {
            id: 'navmenuh'
        },
    },
    verifyCollapse: function () {
        var body = $('body');
        var iscollapse = !body.hasClass(this.class.body.name);
        if (iscollapse) {
            localStorage.setItem(this.class.body.id, true);
        } else {
            localStorage.removeItem(this.class.body.id);
        }
    },
    initial: function () {
        console.log(localStorage);
        var body = $('body');
        if (body.hasClass('layout-top-nav')) {
            [this.class.navmenuv.id, this.class.navmenuvoption.id, this.class.navmenuvsingle.id].forEach(k => localStorage.removeItem(k));
        } else if (body.hasClass('layout-fixed')) {
            [this.class.navmenuh.id, this.class.navmenuhtab.id].forEach(k => localStorage.removeItem(k));
        }
        // vertical
        if (localStorage.getItem(this.class.body.id)) {
            body.addClass(this.class.body.name);
        }
        if (localStorage.getItem(this.class.navmenuv.id)) {
            var navmenuv = $('.nav-menuv[data-id="' + localStorage.getItem(this.class.navmenuv.id) + '"]');
            navmenuv.parent().addClass('menu-is-opening menu-open');
            navmenuv.addClass('active');
            if (localStorage.getItem(this.class.navmenuvoption.id)) {
                var navmenuvoption = navmenuv.parent().find('.nav-treeview .nav-menuv-option[data-id="' + localStorage.getItem(this.class.navmenuvoption.id) + '"]');
                navmenuvoption.addClass('active');
            }
        }
        if (localStorage.getItem(this.class.navmenuvsingle.id)) {
            var navmenuvsingle = $('.nav-menuv-single[data-id="' + localStorage.getItem(this.class.navmenuvsingle.id) + '"]');
            navmenuvsingle.addClass('active');
        }
        // horizonal
        if (localStorage.getItem(this.class.navmenuhtab.id)) {
            var navtab = $('.nav-tabs-module a[href="' + localStorage.getItem(this.class.navmenuhtab.id) + '"]');
            navtab.tab('show');
            if (localStorage.getItem(this.class.navmenuh.id)) {
                $('.nav-menuh[data-id="' + localStorage.getItem(this.class.navmenuh.id) + '"]').addClass('module-selected');
            }
        }
    }
};

$(function () {

    $('[data-toggle="tooltip"]').tooltip();

    $('.table')
        .on('draw.dt', function () {
            $('[data-toggle="tooltip"]').tooltip();
        })
        .on('click', 'img', function () {
            var src = $(this).attr('src');
            load_image(src);
        });

    // Vertical

    $('.collapsedMenu').on('click', function () {
        sidebar.verifyCollapse();
    });

    $('.nav-menuv').on('click', function () {
        $('.nav-menuv').removeClass('active');
        $('.nav-menuv-option').removeClass('active');
        var parent = $(this).parent();
        if (!parent.hasClass(sidebar.class.navmenuv.name)) {
            $(this).addClass('active');
            localStorage.setItem(sidebar.class.navmenuv.id, $(this).data('id'));
        } else {
            $(this).removeClass('active');
            localStorage.removeItem(sidebar.class.navmenuv.id);
        }
        $('.nav-menuv-single').removeClass('active');
        localStorage.removeItem(sidebar.class.navmenuvsingle.id);
    });

    $('.nav-menuv-single').on('click', function () {
        $(this).addClass('active');
        localStorage.removeItem(sidebar.class.navmenuv.id);
        localStorage.removeItem(sidebar.class.navmenuvoption.id);
        localStorage.setItem(sidebar.class.navmenuvsingle.id, $(this).data('id'));
    });

    $('.nav-menuv-option').on('click', function () {
        $(this).addClass('active');
        localStorage.setItem(sidebar.class.navmenuvoption.id, $(this).data('id'));
    });

    // Horizontal

    $('.nav-menuh-tab').on('click', function () {
        var href = $(this).attr('href');
        localStorage.setItem(sidebar.class.navmenuhtab.id, href);
    });

    $('.nav-menuh').on('click', function () {
        $(this).addClass('active');
        localStorage.setItem(sidebar.class.navmenuh.id, $(this).data('id'));
    });

    // logout

    $('.btnLogout').on('click', function () {
        localStorage.clear();
    });

    sidebar.initial();
});