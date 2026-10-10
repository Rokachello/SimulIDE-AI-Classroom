/***************************************************************************
 *   Copyright (C) 2023 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include "mcusleep.h"

class PicSleep : public McuSleep
{
    public:
        PicSleep( eMcu* mcu, QString name );
        ~PicSleep();
};
