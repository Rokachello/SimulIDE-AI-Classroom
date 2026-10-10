/***************************************************************************
 *   Copyright (C) 2021 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include <QDoubleSpinBox>

class PlotSpinBox : public QDoubleSpinBox
{
    public:
        PlotSpinBox( QWidget* parent );
        ~PlotSpinBox();

        void setUnitStr( QString u ) { m_unit = u; }

        QValidator::State validate( QString& text, int& n ) const override;

    private:
        QDoubleSpinBox* m_this;

        QString m_unit;
};
