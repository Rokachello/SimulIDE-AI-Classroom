/***************************************************************************
 *   Copyright (C) 2021 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include <QDialog>

#include "ui_about.h"

class AboutDialog : public QDialog, private Ui::AboutDialog
{
    Q_OBJECT

    public:
        AboutDialog( QWidget* parent=0 );
};
